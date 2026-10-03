import threading

import httpx

from qs_orchestrator.aggregate import AggregateSource
from qs_orchestrator.contract import Result, Task
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import Availability, Source

TASK = Task(prompt="p")
WAIT = 5


def ok(source_id, content=None, model=None, latency_ms=10_000):
    return Result(
        content=content if content is not None else f"answer-{source_id}",
        source=source_id,
        model=model if model is not None else f"m-{source_id}",
        status="success",
        latency_ms=latency_ms,
    )


def fail(source_id, error="boom"):
    return Result(content="", source=source_id, model="m", status="error", latency_ms=1, error=error)


class FakeSource:
    type = "api"

    def __init__(
        self,
        source_id,
        result,
        *,
        available=True,
        capabilities=frozenset({"text"}),
        barrier=None,
        wait_for=None,
        done=None,
    ):
        self.id = source_id
        self.capabilities = capabilities
        self._result = result
        self._available = available
        self._barrier = barrier
        self._wait_for = wait_for
        self._done = done
        self.executed = []
        self.probed = 0

    def execute(self, task):
        self.executed.append(task)
        if self._barrier is not None:
            self._barrier.wait()
        if self._wait_for is not None:
            self._wait_for.wait(WAIT)
        if self._done is not None:
            self._done.set()
        return self._result

    def availability(self):
        self.probed += 1
        return Availability(self._available, None if self._available else "down")


def test_successful_answers_are_combined_under_source_headers():
    a, b = FakeSource("a", ok("a")), FakeSource("b", ok("b"))
    result = AggregateSource([a, b]).execute(TASK)
    assert isinstance(result, Result)
    assert result.status == "success"
    assert result.source == "aggregate"
    assert result.content == "## a\nanswer-a\n\n## b\nanswer-b"
    assert result.model == "m-a, m-b"
    assert result.error is None
    assert isinstance(result.latency_ms, int)
    assert 0 <= result.latency_ms < 10_000


def test_answers_appear_in_source_order_not_completion_order():
    b_done = threading.Event()
    a = FakeSource("a", ok("a"), wait_for=b_done)
    b = FakeSource("b", ok("b"), done=b_done)
    result = AggregateSource([a, b]).execute(TASK)
    assert result.content == "## a\nanswer-a\n\n## b\nanswer-b"


def test_every_source_runs_concurrently_with_the_same_task():
    barrier = threading.Barrier(2, timeout=WAIT)
    a = FakeSource("a", ok("a"), barrier=barrier)
    b = FakeSource("b", ok("b"), barrier=barrier)
    result = AggregateSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert a.executed == [TASK]
    assert b.executed == [TASK]


def test_waits_for_slow_sources_instead_of_returning_the_first_answer():
    release = threading.Event()
    slow = FakeSource("slow", ok("slow"), wait_for=release)
    fast = FakeSource("fast", ok("fast"))
    timer = threading.Timer(0.05, release.set)
    timer.start()
    try:
        result = AggregateSource([slow, fast]).execute(TASK)
    finally:
        release.set()
        timer.cancel()
    assert result.content == "## slow\nanswer-slow\n\n## fast\nanswer-fast"


def test_partial_success_keeps_only_the_successful_answers():
    a, b = FakeSource("a", fail("a")), FakeSource("b", ok("b"))
    result = AggregateSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert result.content == "## b\nanswer-b"
    assert result.model == "m-b"
    assert result.error is None


def test_identical_models_are_listed_once():
    a = FakeSource("a", ok("a", model="same"))
    b = FakeSource("b", ok("b", model="same"))
    assert AggregateSource([a, b]).execute(TASK).model == "same"


def test_all_sources_failing_returns_one_error_result_in_source_order():
    b_done = threading.Event()
    a = FakeSource("a", fail("a", "boom"), wait_for=b_done)
    b = FakeSource("b", fail("b", "bang"), done=b_done)
    result = AggregateSource([a, b]).execute(TASK)
    assert result.status == "error"
    assert result.source == "aggregate"
    assert result.content == ""
    assert result.model == ""
    assert result.error == "all sources failed: a: boom; b: bang"


def test_failure_without_error_text_reports_its_status():
    result = AggregateSource([FakeSource("a", fail("a", error=None))]).execute(TASK)
    assert result.error == "all sources failed: a: error"


def test_is_itself_a_source_built_on_the_shared_base():
    aggregate = AggregateSource([FakeSource("a", ok("a"))])
    assert isinstance(aggregate, Source)
    assert aggregate.id == "aggregate"
    assert aggregate.type == "composite"
    assert AggregateSource([FakeSource("a", ok("a"))], source_id="all").id == "all"


def test_empty_sources_are_rejected_with_the_class_name():
    try:
        AggregateSource([])
    except ValueError as exc:
        assert str(exc) == "AggregateSource needs at least one source"
    else:
        raise AssertionError("expected ValueError")


def test_capabilities_and_availability_come_from_the_members():
    a = FakeSource("a", ok("a"), available=False, capabilities=frozenset({"text", "vision"}))
    b = FakeSource("b", ok("b"), capabilities=frozenset({"text"}))
    aggregate = AggregateSource([a, b])
    assert aggregate.capabilities == frozenset({"text"})
    assert aggregate.availability() == Availability(True)


def test_composes_with_fallback():
    aggregate = AggregateSource([FakeSource("a", fail("a")), FakeSource("b", fail("b"))])
    c = FakeSource("c", ok("c"))
    result = FallbackSource([aggregate, c]).execute(TASK)
    assert result.status == "success"
    assert result.source == "c"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _omniroute(handler):
    return OmniRouteSource("http://omniroute.test/v1", "k", "configured", client=_client(handler))


def _local(handler):
    return LocalModelSource("http://local.test", "configured", client=_client(handler))


def _omni_answer(request):
    return httpx.Response(
        200, json={"model": "routed", "choices": [{"message": {"content": "from omni"}}]}
    )


def _local_answer(request):
    return httpx.Response(
        200, json={"model": "llama3", "message": {"role": "assistant", "content": "from local"}}
    )


def test_real_sources_both_answer_and_are_combined():
    result = AggregateSource([_omniroute(_omni_answer), _local(_local_answer)]).execute(TASK)
    assert result.status == "success"
    assert result.content == "## omniroute\nfrom omni\n\n## local\nfrom local"
    assert result.model == "routed, llama3"


def test_real_sources_one_down_the_other_still_answers():
    omniroute = _omniroute(lambda request: httpx.Response(500, json={"error": "down"}))
    result = AggregateSource([omniroute, _local(_local_answer)]).execute(TASK)
    assert result.status == "success"
    assert result.content == "## local\nfrom local"
    assert result.model == "llama3"
