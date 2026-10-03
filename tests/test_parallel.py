import threading

import httpx
import pytest

from qs_orchestrator.contract import Result, Task
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.parallel import ParallelSource
from qs_orchestrator.source import Availability, Source

TASK = Task(prompt="p")
WAIT = 5


def ok(source_id, latency_ms=10_000):
    return Result(
        content="answer", source=source_id, model="m", status="success", latency_ms=latency_ms
    )


def fail(source_id, error="boom"):
    return Result(content="", source=source_id, model="m", status="error", latency_ms=1, error=error)


class ObservedFailure:
    """Failed Result stand-in that fires an event when its error text is read.

    Reading happens on the calling thread while it processes this failure, so
    anything waiting on the event can only finish after this failure has been
    recorded. That pins the completion order without relying on timing.
    """

    status = "error"

    def __init__(self, error, read):
        self._error = error
        self._read = read

    @property
    def error(self):
        self._read.set()
        return self._error


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


def test_sources_run_concurrently_with_the_same_task():
    barrier = threading.Barrier(2, timeout=WAIT)
    a = FakeSource("a", ok("a"), barrier=barrier)
    b = FakeSource("b", ok("b"), barrier=barrier)
    result = ParallelSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert a.executed == [TASK]
    assert b.executed == [TASK]


def test_fastest_success_wins_without_waiting_for_the_slow_source():
    release = threading.Event()
    slow_finished = threading.Event()
    slow = FakeSource("slow", ok("slow"), wait_for=release, done=slow_finished)
    fast = FakeSource("fast", ok("fast"))
    try:
        result = ParallelSource([slow, fast]).execute(TASK)
        assert not slow_finished.is_set()
    finally:
        release.set()
    assert result.status == "success"
    assert result.source == "fast"
    assert result.content == "answer"


def test_an_early_failure_does_not_beat_a_later_success():
    a_done = threading.Event()
    a = FakeSource("a", fail("a"), done=a_done)
    b = FakeSource("b", ok("b"), wait_for=a_done)
    result = ParallelSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert result.source == "b"


def test_all_failing_reports_failures_in_source_order_not_completion_order():
    b_recorded = threading.Event()
    a = FakeSource("a", fail("a", "boom"), wait_for=b_recorded)
    b = FakeSource("b", ObservedFailure("bang", b_recorded))
    result = ParallelSource([a, b]).execute(TASK)
    assert isinstance(result, Result)
    assert result.status == "error"
    assert result.source == "parallel"
    assert result.content == ""
    assert result.model == ""
    assert result.error == "all sources failed: a: boom; b: bang"


def test_failure_without_error_text_reports_its_status():
    result = ParallelSource([FakeSource("a", fail("a", error=None))]).execute(TASK)
    assert result.error == "all sources failed: a: error"


def test_latency_is_total_time_not_the_winning_sources_own():
    result = ParallelSource([FakeSource("a", ok("a", latency_ms=10_000))]).execute(TASK)
    assert isinstance(result.latency_ms, int)
    assert 0 <= result.latency_ms < 10_000


def test_requires_at_least_one_source():
    with pytest.raises(ValueError):
        ParallelSource([])


def test_is_itself_a_source():
    parallel = ParallelSource([FakeSource("a", ok("a"))])
    assert isinstance(parallel, Source)
    assert parallel.id == "parallel"
    assert parallel.type == "composite"
    assert ParallelSource([FakeSource("a", ok("a"))], source_id="race").id == "race"


def test_capabilities_are_the_intersection_of_members():
    a = FakeSource("a", ok("a"), capabilities=frozenset({"text", "vision"}))
    b = FakeSource("b", ok("b"), capabilities=frozenset({"text"}))
    assert ParallelSource([a, b]).capabilities == frozenset({"text"})


def test_availability_true_as_soon_as_one_member_is_available():
    a = FakeSource("a", ok("a"), available=False)
    b = FakeSource("b", ok("b"))
    c = FakeSource("c", ok("c"))
    assert ParallelSource([a, b, c]).availability() == Availability(True)
    assert (a.probed, b.probed, c.probed) == (1, 1, 0)


def test_availability_false_lists_every_member():
    a = FakeSource("a", ok("a"), available=False)
    b = FakeSource("b", ok("b"), available=False)
    availability = ParallelSource([a, b]).availability()
    assert availability.available is False
    assert availability.detail == "a: down; b: down"


def test_composes_with_fallback():
    parallel = ParallelSource([FakeSource("a", fail("a")), FakeSource("b", fail("b"))])
    c = FakeSource("c", ok("c"))
    result = FallbackSource([parallel, c]).execute(TASK)
    assert result.status == "success"
    assert result.source == "c"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _omniroute(handler):
    return OmniRouteSource("http://omniroute.test/v1", "k", "configured", client=_client(handler))


def _local(handler):
    return LocalModelSource("http://local.test", "configured", client=_client(handler))


def test_real_sources_omniroute_down_local_answers():
    omniroute = _omniroute(lambda request: httpx.Response(500, json={"error": "down"}))
    local = _local(
        lambda request: httpx.Response(
            200, json={"model": "llama3", "message": {"role": "assistant", "content": "hi"}}
        )
    )
    result = ParallelSource([omniroute, local]).execute(TASK)
    assert result.status == "success"
    assert result.source == "local"
    assert result.model == "llama3"
    assert result.content == "hi"


def test_real_sources_all_down_reports_both_failures_in_order():
    def down(request):
        raise httpx.ConnectError("unreachable", request=request)

    result = ParallelSource([_omniroute(down), _local(down)]).execute(TASK)
    assert result.status == "error"
    assert result.source == "parallel"
    assert result.error.startswith("all sources failed: omniroute: ConnectError")
    assert "; local: ConnectError" in result.error
