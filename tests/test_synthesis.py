import json

import httpx

from qs_orchestrator.contract import Attempt, Result, Task
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.sequential import SequentialSource
from qs_orchestrator.source import Availability, Source
from qs_orchestrator.synthesis import DEFAULT_PROMPT, synthesize

TASK = Task(prompt="topic", context=["doc"], system="Be brief.")


def ok(source_id, content=None):
    return Result(
        content=content if content is not None else f"out-{source_id}",
        source=source_id,
        model=f"m-{source_id}",
        status="success",
        latency_ms=7,
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
    capabilities = frozenset({"text"})

    def __init__(self, source_id, result, *, available=True):
        self.id = source_id
        self._result = result
        self._available = available
        self.tasks = []

    def execute(self, task):
        self.tasks.append(task)
        return self._result

    def availability(self):
        return Availability(self._available, None if self._available else "down")


def labelled(*names):
    return "\n\n".join(f"## {name}\nout-{name}" for name in names)


def expected_prompt(question, answers, prompt=DEFAULT_PROMPT):
    return prompt.replace("{input}", question).replace("{previous}", answers)


def test_every_source_gets_the_original_task():
    a, b = FakeSource("a", ok("a")), FakeSource("b", ok("b"))
    synthesize([a, b], FakeSource("synth", ok("synth", "final"))).execute(TASK)
    assert a.tasks == [TASK]
    assert b.tasks == [TASK]


def test_the_synthesizer_sees_the_question_and_the_labelled_answers():
    a, b = FakeSource("a", ok("a")), FakeSource("b", ok("b"))
    synth = FakeSource("synth", ok("synth", "final"))
    result = synthesize([a, b], synth).execute(TASK)
    (task,) = synth.tasks
    assert task.prompt == expected_prompt("topic", labelled("a", "b"))
    assert "topic" in task.prompt
    assert labelled("a", "b") in task.prompt
    assert task.context == ["doc"]
    assert task.system == "Be brief."
    assert result.status == "success"
    assert (result.source, result.model, result.content) == ("synth", "m-synth", "final")


def test_the_default_prompt_has_both_placeholders():
    assert "{input}" in DEFAULT_PROMPT
    assert "{previous}" in DEFAULT_PROMPT


def test_a_custom_prompt_replaces_the_default():
    synth = FakeSource("synth", ok("synth"))
    synthesize([FakeSource("a", ok("a"))], synth, prompt="Merge only: {previous}").execute(TASK)
    assert synth.tasks[0].prompt == "Merge only: ## a\nout-a"


def test_the_trail_lists_every_source_then_the_synthesizer():
    sources = [FakeSource("a", ok("a")), FakeSource("b", ok("b"))]
    result = synthesize(sources, FakeSource("synth", ok("synth"))).execute(TASK)
    assert result.attempts == (won("a"), won("b"), won("synth"))


def test_failed_sources_are_left_out_of_the_synthesis_but_stay_in_the_trail():
    synth = FakeSource("synth", ok("synth"))
    sources = [FakeSource("a", fail("a")), FakeSource("b", ok("b"))]
    result = synthesize(sources, synth).execute(TASK)
    assert synth.tasks[0].prompt == expected_prompt("topic", labelled("b"))
    assert result.status == "success"
    assert result.attempts == (lost("a"), won("b"), won("synth"))


def test_when_every_source_fails_the_synthesizer_is_not_called():
    synth = FakeSource("synth", ok("synth"))
    sources = [FakeSource("a", fail("a", "boom")), FakeSource("b", fail("b", "bang"))]
    result = synthesize(sources, synth).execute(TASK)
    assert result.status == "error"
    assert result.source == "synthesis"
    assert result.error == "step 1 of 2 (aggregate) failed: all sources failed: a: boom; b: bang"
    assert synth.tasks == []


def test_a_failing_synthesizer_is_reported_with_the_trail_so_far():
    sources = [FakeSource("a", ok("a"))]
    result = synthesize(sources, FakeSource("synth", fail("synth"))).execute(TASK)
    assert result.status == "error"
    assert result.error == "step 2 of 2 (synth) failed: boom"
    assert result.attempts == (won("a"), lost("synth"))


def test_it_is_a_source_with_a_configurable_id():
    flow = synthesize([FakeSource("a", ok("a"))], FakeSource("synth", ok("synth")))
    assert isinstance(flow, SequentialSource)
    assert isinstance(flow, Source)
    assert flow.id == "synthesis"
    renamed = synthesize(
        [FakeSource("a", fail("a"))], FakeSource("synth", ok("synth")), source_id="merge"
    )
    assert renamed.id == "merge"
    assert renamed.execute(TASK).source == "merge"


def test_available_needs_one_working_source_and_the_synthesizer():
    synth = FakeSource("synth", ok("synth"))
    partly = synthesize([FakeSource("a", ok("a"), available=False), FakeSource("b", ok("b"))], synth)
    assert partly.availability() == Availability(True)
    none = synthesize([FakeSource("a", ok("a"), available=False)], synth)
    assert none.availability() == Availability(False, "aggregate: a: down")
    no_synth = synthesize([FakeSource("a", ok("a"))], FakeSource("s", ok("s"), available=False))
    assert no_synth.availability() == Availability(False, "s: down")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_real_sources_the_synthesizer_request_contains_both_answers():
    seen = {}

    def synth_handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"model": "big", "choices": [{"message": {"content": "merged"}}]}
        )

    first = OmniRouteSource(
        "http://omniroute.test/v1",
        "k",
        "m1",
        client=_client(
            lambda request: httpx.Response(
                200, json={"model": "m1", "choices": [{"message": {"content": "from omni"}}]}
            )
        ),
    )
    second = LocalModelSource(
        "http://local.test",
        "m2",
        client=_client(
            lambda request: httpx.Response(
                200, json={"model": "llama3", "message": {"role": "assistant", "content": "from local"}}
            )
        ),
    )
    synth = OmniRouteSource(
        "http://omniroute.test/v1", "k", "big", source_id="synth", client=_client(synth_handler)
    )
    result = synthesize([first, second], synth).execute(Task(prompt="cats"))
    assert result.status == "success"
    assert (result.source, result.content) == ("synth", "merged")
    (message,) = seen["body"]["messages"]
    assert message["content"] == expected_prompt(
        "cats", "## omniroute\nfrom omni\n\n## local\nfrom local"
    )
    assert [a.source for a in result.attempts] == ["omniroute", "local", "synth"]
