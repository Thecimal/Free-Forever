import json

import httpx
import pytest

from qs_orchestrator.contract import Attempt, Result, Task
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.sequential import SequentialSource, Step, template
from qs_orchestrator.source import Availability, Source

TASK = Task(prompt="topic")


def ok(source_id, content=None, latency_ms=7):
    return Result(
        content=content if content is not None else f"out-{source_id}",
        source=source_id,
        model=f"m-{source_id}",
        status="success",
        latency_ms=latency_ms,
    )


def fail(source_id, error="boom"):
    return Result(
        content="",
        source=source_id,
        model=f"m-{source_id}",
        status="error",
        latency_ms=3,
        error=error,
    )


def won(source_id):
    return Attempt(source_id, f"m-{source_id}", "success", 7, None)


def lost(source_id, error="boom"):
    return Attempt(source_id, f"m-{source_id}", "error", 3, error)


class FakeSource:
    type = "api"

    def __init__(self, source_id, result, *, available=True, capabilities=frozenset({"text"})):
        self.id = source_id
        self.capabilities = capabilities
        self._result = result
        self._available = available
        self.tasks = []
        self.probed = 0

    def execute(self, task):
        self.tasks.append(task)
        return self._result

    def availability(self):
        self.probed += 1
        return Availability(self._available, None if self._available else "down")


def test_steps_run_in_order_each_building_on_the_previous_answer():
    a, b, c = (FakeSource(name, ok(name)) for name in "abc")
    workflow = SequentialSource(
        [
            Step(a, template("Research: {input}")),
            Step(b, template("Analyze: {previous}")),
            Step(c, template("Critique {previous} of {input}")),
        ]
    )
    result = workflow.execute(TASK)
    assert [t.prompt for t in a.tasks] == ["Research: topic"]
    assert [t.prompt for t in b.tasks] == ["Analyze: out-a"]
    assert [t.prompt for t in c.tasks] == ["Critique out-b of topic"]
    assert result.status == "success"
    assert result.content == "out-c"


def test_the_final_step_answers_with_total_latency_and_the_whole_trail():
    sources = [FakeSource(name, ok(name, latency_ms=10_000)) for name in "ab"]
    workflow = SequentialSource([Step(s, template("{previous}")) for s in sources])
    result = workflow.execute(TASK)
    assert (result.source, result.model) == ("b", "m-b")
    assert 0 <= result.latency_ms < 10_000
    assert [(a.source, a.status) for a in result.attempts] == [("a", "success"), ("b", "success")]


def test_builders_see_the_original_task_and_the_previous_result():
    seen = []

    def spy(original, previous):
        seen.append((original, previous))
        return Task(prompt="p")

    a, b = FakeSource("a", ok("a")), FakeSource("b", ok("b"))
    SequentialSource([Step(a, spy), Step(b, spy)]).execute(TASK)
    assert seen[0] == (TASK, None)
    assert seen[1][0] is TASK
    assert seen[1][1].source == "a"


def test_a_failing_step_stops_the_workflow_and_names_the_step():
    a, b, c = FakeSource("a", ok("a")), FakeSource("b", fail("b")), FakeSource("c", ok("c"))
    workflow = SequentialSource([Step(s, template("{previous}")) for s in (a, b, c)])
    result = workflow.execute(TASK)
    assert result.status == "error"
    assert result.source == "sequential"
    assert (result.content, result.model) == ("", "")
    assert result.error == "step 2 of 3 (b) failed: boom"
    assert result.attempts == (won("a"), lost("b"))
    assert c.tasks == []


def test_failure_without_error_text_reports_its_status():
    a = FakeSource("a", fail("a", error=None))
    result = SequentialSource([Step(a, template("{input}"))]).execute(TASK)
    assert result.error == "step 1 of 1 (a) failed: error"


def test_an_exception_from_a_builder_is_not_swallowed():
    def broken(original, previous):
        raise RuntimeError("bad builder")

    workflow = SequentialSource([Step(FakeSource("a", ok("a")), broken)])
    with pytest.raises(RuntimeError):
        workflow.execute(TASK)


def test_template_fills_placeholders_in_a_single_pass():
    build = template("{input} / {previous}")
    first = build(Task(prompt="use {previous}"), None)
    assert first.prompt == "use {previous} / "
    second = build(Task(prompt="use {previous}"), ok("a", content="X {input}"))
    assert second.prompt == "use {previous} / X {input}"


def test_template_leaves_other_braces_alone():
    task = template('{"k": "{input}", "other": {other}}')(Task(prompt="v"), None)
    assert task.prompt == '{"k": "v", "other": {other}}'


def test_template_keeps_context_and_system_unless_overridden():
    original = Task(prompt="p", context=["doc"], system="sys")
    kept = template("{input}")(original, None)
    assert (kept.context, kept.system) == (["doc"], "sys")
    assert kept.context is not original.context
    assert template("{input}", system="other")(original, None).system == "other"


def test_empty_workflow_is_rejected():
    with pytest.raises(ValueError) as info:
        SequentialSource([])
    assert str(info.value) == "SequentialSource needs at least one source"


def test_is_itself_a_source_built_on_the_shared_base():
    a = FakeSource("a", ok("a"), capabilities=frozenset({"text", "vision"}))
    b = FakeSource("b", ok("b"), capabilities=frozenset({"text"}))
    workflow = SequentialSource([Step(a, template("{input}")), Step(b, template("{previous}"))])
    assert isinstance(workflow, Source)
    assert (workflow.id, workflow.type) == ("sequential", "composite")
    assert workflow.capabilities == frozenset({"text"})
    renamed = SequentialSource([Step(a, template("{input}"))], source_id="flow")
    assert renamed.id == "flow"


def test_available_only_when_every_step_is_available():
    a = FakeSource("a", ok("a"))
    b = FakeSource("b", ok("b"), available=False)
    c = FakeSource("c", ok("c"), available=False)
    everything = SequentialSource([Step(s, template("{input}")) for s in (a, a)])
    assert everything.availability() == Availability(True)
    broken = SequentialSource([Step(s, template("{input}")) for s in (a, b, c)])
    availability = broken.availability()
    assert availability.available is False
    assert availability.detail == "b: down; c: down"
    assert (b.probed, c.probed) == (1, 1)


def test_a_failed_workflow_falls_through_in_a_fallback_with_a_flat_trail():
    a, b = FakeSource("a", ok("a")), FakeSource("b", fail("b"))
    workflow = SequentialSource([Step(s, template("{input}")) for s in (a, b)])
    backup = FakeSource("backup", ok("backup"))
    result = FallbackSource([workflow, backup]).execute(TASK)
    assert result.source == "backup"
    assert result.attempts == (won("a"), lost("b"), won("backup"))


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_real_sources_the_second_request_carries_the_first_answer():
    seen = {}

    def local_handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"model": "llama3", "message": {"role": "assistant", "content": "polished"}}
        )

    omniroute = OmniRouteSource(
        "http://omniroute.test/v1",
        "k",
        "configured",
        client=_client(
            lambda request: httpx.Response(
                200, json={"model": "routed", "choices": [{"message": {"content": "draft"}}]}
            )
        ),
    )
    local = LocalModelSource("http://local.test", "configured", client=_client(local_handler))
    workflow = SequentialSource(
        [
            Step(omniroute, template("Write about {input}")),
            Step(local, template("Improve: {previous}")),
        ]
    )
    result = workflow.execute(Task(prompt="cats", system="Be brief."))
    assert result.status == "success"
    assert (result.source, result.content) == ("local", "polished")
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Improve: draft"},
    ]
    assert [a.source for a in result.attempts] == ["omniroute", "local"]
