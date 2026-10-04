import threading

import httpx

from qs_orchestrator.aggregate import AggregateSource
from qs_orchestrator.composite import attempts_from
from qs_orchestrator.contract import Attempt, Result, Task
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.parallel import ParallelSource

TASK = Task(prompt="p")
WAIT = 5


def ok(source_id, latency_ms=7):
    return Result(
        content=f"answer-{source_id}",
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
    capabilities = frozenset({"text"})

    def __init__(self, source_id, result, *, wait_for=None):
        self.id = source_id
        self._result = result
        self._wait_for = wait_for

    def execute(self, task):
        if self._wait_for is not None:
            self._wait_for.wait(WAIT)
        return self._result

    def availability(self):
        raise AssertionError("not used")


class ObservedFailure:
    """A failed Result that fires an event when its error text is read.

    The caller reads the error while recording this failure, so anything
    waiting on the event can only proceed after the failure was recorded.
    """

    status = "error"
    latency_ms = 3
    attempts = ()

    def __init__(self, source_id, error, read):
        self.source = source_id
        self.model = f"m-{source_id}"
        self._error = error
        self._read = read

    @property
    def error(self):
        self._read.set()
        return self._error


def test_result_has_no_attempts_by_default():
    assert Result("c", "s", "m", "success", 1).attempts == ()


def test_plain_sources_leave_attempts_empty():
    def handler(request):
        status = 200 if "ok" in str(request.url) else 500
        body = {"choices": [{"message": {"content": "hi"}}]} if status == 200 else {}
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    good = OmniRouteSource("http://ok.test/v1", "k", "m", client=client).execute(TASK)
    bad = OmniRouteSource("http://bad.test/v1", "k", "m", client=client).execute(TASK)
    assert good.status == "success" and good.attempts == ()
    assert bad.status == "error" and bad.attempts == ()


def test_attempts_from_describes_plain_results_one_entry_each():
    assert attempts_from([]) == ()
    assert attempts_from([fail("a"), ok("b")]) == (lost("a"), won("b"))


def test_attempts_from_uses_a_members_own_trail_instead_of_wrapping_it():
    inner = Result("", "inner", "", "error", 9, "all sources failed", attempts=(lost("x"), lost("y")))
    assert attempts_from([inner, ok("z")]) == (lost("x"), lost("y"), won("z"))


def test_fallback_records_the_failure_and_the_winner():
    result = FallbackSource([FakeSource("a", fail("a")), FakeSource("b", ok("b"))]).execute(TASK)
    assert result.source == "b"
    assert result.error is None
    assert result.attempts == (lost("a"), won("b"))


def test_fallback_stops_recording_at_the_first_success():
    result = FallbackSource([FakeSource("a", ok("a")), FakeSource("b", ok("b"))]).execute(TASK)
    assert result.attempts == (won("a"),)


def test_fallback_records_every_failure_when_all_fail():
    sources = [FakeSource("a", fail("a")), FakeSource("b", fail("b", "bang"))]
    result = FallbackSource(sources).execute(TASK)
    assert result.status == "error"
    assert result.attempts == (lost("a"), lost("b", "bang"))


def test_aggregate_records_partial_failures_without_marking_the_result_failed():
    result = AggregateSource([FakeSource("a", fail("a")), FakeSource("b", ok("b"))]).execute(TASK)
    assert result.status == "success"
    assert result.error is None
    assert result.content == "## b\nanswer-b"
    assert result.attempts == (lost("a"), won("b"))


def test_aggregate_records_every_failure_when_all_fail():
    sources = [FakeSource("a", fail("a")), FakeSource("b", fail("b", "bang"))]
    result = AggregateSource(sources).execute(TASK)
    assert result.status == "error"
    assert result.attempts == (lost("a"), lost("b", "bang"))


def test_parallel_records_failures_that_finished_before_the_winner():
    a_recorded = threading.Event()
    a = FakeSource("a", ObservedFailure("a", "boom", a_recorded))
    b = FakeSource("b", ok("b"), wait_for=a_recorded)
    result = ParallelSource([a, b]).execute(TASK)
    assert result.source == "b"
    assert result.attempts == (lost("a"), won("b"))


def test_parallel_trail_leaves_out_members_still_running():
    release = threading.Event()
    slow = FakeSource("slow", ok("slow"), wait_for=release)
    fast = FakeSource("fast", ok("fast"))
    try:
        result = ParallelSource([slow, fast]).execute(TASK)
    finally:
        release.set()
    assert result.source == "fast"
    assert result.attempts == (won("fast"),)


def test_parallel_records_every_failure_in_source_order_when_all_fail():
    sources = [FakeSource("a", fail("a")), FakeSource("b", fail("b", "bang"))]
    result = ParallelSource(sources).execute(TASK)
    assert result.status == "error"
    assert result.attempts == (lost("a"), lost("b", "bang"))


def test_nested_composites_flatten_to_the_sources_that_did_the_work():
    inner = AggregateSource(
        [FakeSource("a", fail("a")), FakeSource("b", fail("b", "bang"))], source_id="agg"
    )
    result = FallbackSource([inner, FakeSource("c", ok("c"))]).execute(TASK)
    assert result.source == "c"
    assert result.attempts == (lost("a"), lost("b", "bang"), won("c"))


def test_a_winning_nested_composite_is_not_double_counted():
    result = FallbackSource([ParallelSource([FakeSource("a", ok("a"))])]).execute(TASK)
    assert result.attempts == (won("a"),)
