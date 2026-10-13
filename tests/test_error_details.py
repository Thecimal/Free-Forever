import httpx

from qs_orchestrator.contract import Task
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource

TASK = Task(prompt="p")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def omniroute(handler, key="k"):
    return OmniRouteSource("http://omniroute.test/v1", key, "m", client=_client(handler))


def local(handler):
    return LocalModelSource("http://local.test", "m", client=_client(handler))


def test_a_failed_request_includes_the_servers_explanation():
    source = omniroute(
        lambda request: httpx.Response(
            503, json={"error": {"message": "no providers available for this combo"}}
        )
    )
    error = source.execute(TASK).error
    assert error.startswith("HTTPStatusError: Server error '503 Service Unavailable'")
    assert " | response: " in error
    assert "no providers available for this combo" in error


def test_the_mozilla_help_line_is_dropped():
    source = omniroute(lambda request: httpx.Response(503, text="down"))
    error = source.execute(TASK).error
    assert "developer.mozilla.org" not in error
    assert "\n" not in error


def test_the_response_is_collapsed_to_one_line_and_shortened():
    source = omniroute(lambda request: httpx.Response(500, text="a\n\n  b " + "x" * 1000))
    error = source.execute(TASK).error
    assert "\n" not in error
    assert " | response: a b xxx" in error
    assert "x" * 280 in error
    assert "x" * 400 not in error


def test_an_empty_response_adds_nothing():
    error = omniroute(lambda request: httpx.Response(502)).execute(TASK).error
    assert "response:" not in error
    assert error.startswith("HTTPStatusError: Server error '502")


def test_the_api_key_is_redacted_from_the_response():
    source = omniroute(
        lambda request: httpx.Response(401, text="invalid key SECRET-KEY-123 for user"),
        key="SECRET-KEY-123",
    )
    result = source.execute(TASK)
    assert "SECRET-KEY-123" not in result.error
    assert "invalid key *** for user" in result.error
    assert "SECRET-KEY-123" not in source.availability().detail


def test_a_short_placeholder_key_is_not_replaced_in_the_response():
    source = omniroute(lambda request: httpx.Response(401, text="invalid api key"), key="k")
    assert source.execute(TASK).error.endswith(" | response: invalid api key")


def test_availability_includes_the_servers_explanation_too():
    source = omniroute(lambda request: httpx.Response(401, text="invalid api key"))
    availability = source.availability()
    assert availability.available is False
    assert availability.detail.startswith("HTTPStatusError: Client error '401")
    assert availability.detail.endswith(" | response: invalid api key")


def test_the_local_source_gets_the_same_detail():
    error = local(lambda request: httpx.Response(404, text='{"error": "model not found"}')).execute(
        TASK
    ).error
    assert error.startswith("HTTPStatusError: Client error '404")
    assert error.endswith(' | response: {"error": "model not found"}')


def test_other_errors_keep_their_plain_form():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    error = omniroute(refuse).execute(TASK).error
    assert error == "ConnectError: refused"
