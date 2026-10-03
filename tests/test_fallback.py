import httpx
import pytest

from qs_orchestrator.contract import Result, Task
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import Availability, Source

TASK = Task(prompt="p")


def ok(source_id, latency_ms=10_000):
    return Result(
        content="answer", source=source_id, model="m", status="success", latency_ms=latency_ms
    )


def fail(source_id, error="boom"):
    return Result(content="", source=source_id, model="m", status="error", latency_ms=1, error=error)


class FakeSource:
    type = "api"

    def __init__(self, source_id, result, *, available=True, capabilities=frozenset({"text"})):
        self.id = source_id
        self.capabilities = capabilities
        self._result = result
        self._available = available
        self.executed = []
        self.probed = 0

    def execute(self, task):
        self.executed.append(task)
        return self._result

    def availability(self):
        self.probed += 1
        return Availability(self._available, None if self._available else "down")


def test_first_success_wins_and_later_sources_are_not_called():
    a, b = FakeSource("a", ok("a")), FakeSource("b", ok("b"))
    result = FallbackSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert result.source == "a"
    assert result.content == "answer"
    assert a.executed == [TASK]
    assert b.executed == []


def test_failure_falls_through_to_next_source_in_order():
    a, b = FakeSource("a", fail("a")), FakeSource("b", ok("b"))
    result = FallbackSource([a, b]).execute(TASK)
    assert result.status == "success"
    assert result.source == "b"
    assert result.model == "m"
    assert a.executed == [TASK]
    assert b.executed == [TASK]


def test_latency_is_total_time_not_the_winning_sources_own():
    result = FallbackSource([FakeSource("a", ok("a", latency_ms=10_000))]).execute(TASK)
    assert isinstance(result.latency_ms, int)
    assert 0 <= result.latency_ms < 10_000


def test_all_sources_failing_returns_one_error_result_listing_every_failure():
    a = FakeSource("a", fail("a", "boom"))
    b = FakeSource("b", fail("b", "bang"))
    result = FallbackSource([a, b]).execute(TASK)
    assert isinstance(result, Result)
    assert result.status == "error"
    assert result.source == "fallback"
    assert result.content == ""
    assert result.model == ""
    assert result.error == "all sources failed: a: boom; b: bang"
    assert a.executed == [TASK] and b.executed == [TASK]


def test_failure_without_error_text_reports_its_status():
    result = FallbackSource([FakeSource("a", fail("a", error=None))]).execute(TASK)
    assert result.error == "all sources failed: a: error"


def test_requires_at_least_one_source():
    with pytest.raises(ValueError):
        FallbackSource([])


def test_is_itself_a_source():
    fallback = FallbackSource([FakeSource("a", ok("a"))])
    assert isinstance(fallback, Source)
    assert fallback.id == "fallback"
    assert fallback.type == "composite"
    assert FallbackSource([FakeSource("a", ok("a"))], source_id="pool").id == "pool"


def test_capabilities_are_the_intersection_of_members():
    a = FakeSource("a", ok("a"), capabilities=frozenset({"text", "vision"}))
    b = FakeSource("b", ok("b"), capabilities=frozenset({"text"}))
    assert FallbackSource([a, b]).capabilities == frozenset({"text"})


def test_availability_true_as_soon_as_one_member_is_available():
    a = FakeSource("a", ok("a"), available=False)
    b = FakeSource("b", ok("b"))
    c = FakeSource("c", ok("c"))
    assert FallbackSource([a, b, c]).availability() == Availability(True)
    assert (a.probed, b.probed, c.probed) == (1, 1, 0)


def test_availability_false_lists_every_member():
    a = FakeSource("a", ok("a"), available=False)
    b = FakeSource("b", ok("b"), available=False)
    availability = FallbackSource([a, b]).availability()
    assert availability.available is False
    assert availability.detail == "a: down; b: down"


def test_fallbacks_nest():
    inner = FallbackSource([FakeSource("a", fail("a"))], source_id="inner")
    b = FakeSource("b", ok("b"))
    result = FallbackSource([inner, b]).execute(TASK)
    assert result.status == "success"
    assert result.source == "b"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _omniroute(handler):
    return OmniRouteSource("http://omniroute.test/v1", "k", "configured", client=_client(handler))


def _local(handler):
    return LocalModelSource("http://local.test", "configured", client=_client(handler))


def test_real_sources_omniroute_down_falls_back_to_local():
    omniroute = _omniroute(lambda request: httpx.Response(500, json={"error": "down"}))
    local = _local(
        lambda request: httpx.Response(
            200, json={"model": "llama3", "message": {"role": "assistant", "content": "hi"}}
        )
    )
    result = FallbackSource([omniroute, local]).execute(TASK)
    assert result.status == "success"
    assert result.source == "local"
    assert result.model == "llama3"
    assert result.content == "hi"


def test_real_sources_all_down_reports_both_failures():
    def down(request):
        raise httpx.ConnectError("unreachable", request=request)

    result = FallbackSource([_omniroute(down), _local(down)]).execute(TASK)
    assert result.status == "error"
    assert result.source == "fallback"
    assert result.error.startswith("all sources failed: omniroute: ConnectError")
    assert "; local: ConnectError" in result.error
