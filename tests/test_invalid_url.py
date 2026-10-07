import httpx
import pytest

from qs_orchestrator.contract import Task
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource

TASK = Task(prompt="p")


def _mock_client():
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )


def make_omniroute(client):
    return OmniRouteSource("http://localhost:PORT/v1", "k", "m", client=client)


def make_local(client):
    return LocalModelSource("http://localhost:PORT", "m", client=client)


@pytest.mark.parametrize("use_client", [False, True])
@pytest.mark.parametrize("make", [make_omniroute, make_local])
def test_an_invalid_url_becomes_an_error_result(make, use_client):
    result = make(_mock_client() if use_client else None).execute(TASK)
    assert result.status == "error"
    assert result.content == ""
    assert result.model == "m"
    assert result.error.startswith("InvalidURL: Invalid port: 'PORT'")


@pytest.mark.parametrize("use_client", [False, True])
@pytest.mark.parametrize("make", [make_omniroute, make_local])
def test_an_invalid_url_makes_the_source_unavailable(make, use_client):
    availability = make(_mock_client() if use_client else None).availability()
    assert availability.available is False
    assert availability.detail.startswith("InvalidURL: Invalid port: 'PORT'")
