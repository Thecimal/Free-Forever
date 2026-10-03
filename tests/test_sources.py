import json
from dataclasses import asdict, replace

import httpx
import pytest

from qs_orchestrator.contract import Result, Task
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import Availability, Source

OMNI_BASE = "http://omniroute.test/v1"
LOCAL_BASE = "http://local.test"
TASK = Task(prompt="Hello, explain X", context=["doc A", "doc B"])
TASK_TEXT = "doc A\n\ndoc B\n\nHello, explain X"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def make_omniroute(handler):
    return OmniRouteSource(
        OMNI_BASE + "/", "secret-key", "configured-model", client=_client(handler)
    )


def make_local(handler):
    return LocalModelSource(LOCAL_BASE + "/", "configured-model", client=_client(handler))


def omni_body(content="answer", model="routed-model"):
    return {"model": model, "choices": [{"message": {"role": "assistant", "content": content}}]}


def local_body(content="answer", model="routed-model"):
    return {"model": model, "message": {"role": "assistant", "content": content}, "done": True}


SOURCES = [
    pytest.param(make_omniroute, omni_body, "omniroute", "api", id="omniroute"),
    pytest.param(make_local, local_body, "local", "local", id="local"),
]
ARGS = "make, body, source_id, source_type"


@pytest.mark.parametrize(ARGS, SOURCES)
def test_execute_returns_normalized_result(make, body, source_id, source_type):
    source = make(lambda request: httpx.Response(200, json=body("X is a thing.")))
    result = source.execute(TASK)
    assert isinstance(result, Result)
    assert result.content == "X is a thing."
    assert result.source == source_id
    assert result.model == "routed-model"
    assert result.status == "success"
    assert result.error is None
    assert isinstance(result.latency_ms, int) and result.latency_ms >= 0


@pytest.mark.parametrize(ARGS, SOURCES)
def test_source_satisfies_contract(make, body, source_id, source_type):
    source = make(lambda request: httpx.Response(200, json=body()))
    assert isinstance(source, Source)
    assert source.id == source_id
    assert source.type == source_type
    assert source.capabilities == frozenset({"text"})


def test_both_sources_produce_the_same_result_structure():
    omni = make_omniroute(lambda request: httpx.Response(200, json=omni_body())).execute(TASK)
    local = make_local(lambda request: httpx.Response(200, json=local_body())).execute(TASK)
    assert type(omni) is Result and type(local) is Result
    assert asdict(omni).keys() == asdict(local).keys()
    assert replace(omni, source="x", latency_ms=0) == replace(local, source="x", latency_ms=0)
    assert (omni.source, local.source) == ("omniroute", "local")


def test_both_sources_report_failures_in_the_same_structure():
    def server_error(request):
        return httpx.Response(500, json={"error": "boom"})

    omni = make_omniroute(server_error).execute(TASK)
    local = make_local(server_error).execute(TASK)
    for result in (omni, local):
        assert result.status == "error"
        assert result.content == ""
        assert result.model == "configured-model"
        assert "500" in result.error
    mask = {"source": "x", "latency_ms": 0, "error": None}
    assert replace(omni, **mask) == replace(local, **mask)


def test_omniroute_wire_format():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=omni_body())

    make_omniroute(handler).execute(TASK)
    assert seen["method"] == "POST"
    assert seen["url"] == f"{OMNI_BASE}/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"] == {
        "model": "configured-model",
        "messages": [{"role": "user", "content": TASK_TEXT}],
        "temperature": 0.2,
    }


def test_local_wire_format():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=local_body())

    make_local(handler).execute(TASK)
    assert seen["method"] == "POST"
    assert seen["url"] == f"{LOCAL_BASE}/api/chat"
    assert seen["body"] == {
        "model": "configured-model",
        "messages": [{"role": "user", "content": TASK_TEXT}],
        "stream": False,
        "options": {"temperature": 0.2},
    }


@pytest.mark.parametrize(ARGS, SOURCES)
def test_task_without_context_sends_prompt_only(make, body, source_id, source_type):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=body())

    make(handler).execute(Task(prompt="just this"))
    assert seen["body"]["messages"] == [{"role": "user", "content": "just this"}]


@pytest.mark.parametrize(ARGS, SOURCES)
def test_model_falls_back_to_configured_when_response_has_none(
    make, body, source_id, source_type
):
    source = make(lambda request: httpx.Response(200, json=body(model=None)))
    result = source.execute(TASK)
    assert result.status == "success"
    assert result.model == "configured-model"


@pytest.mark.parametrize(ARGS, SOURCES)
def test_http_error_becomes_error_result(make, body, source_id, source_type):
    source = make(lambda request: httpx.Response(500, json={"error": "boom"}))
    result = source.execute(TASK)
    assert result.status == "error"
    assert result.content == ""
    assert result.source == source_id
    assert result.model == "configured-model"
    assert "500" in result.error


@pytest.mark.parametrize(ARGS, SOURCES)
def test_transport_error_becomes_error_result(make, body, source_id, source_type):
    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    result = make(handler).execute(TASK)
    assert result.status == "error"
    assert "ConnectError" in result.error


@pytest.mark.parametrize(
    "response_kwargs",
    [{"json": {}}, {"json": {"unexpected": 1}}, {"content": b"not json"}],
)
@pytest.mark.parametrize(ARGS, SOURCES)
def test_malformed_response_becomes_error_result(
    make, body, source_id, source_type, response_kwargs
):
    source = make(lambda request: httpx.Response(200, **response_kwargs))
    result = source.execute(TASK)
    assert result.status == "error"
    assert result.content == ""
    assert result.error


@pytest.mark.parametrize(ARGS, SOURCES)
def test_null_content_becomes_error_result(make, body, source_id, source_type):
    source = make(lambda request: httpx.Response(200, json=body(content=None)))
    result = source.execute(TASK)
    assert result.status == "error"
    assert result.content == ""


@pytest.mark.parametrize(ARGS, SOURCES)
def test_availability_true_when_endpoint_answers(make, body, source_id, source_type):
    source = make(lambda request: httpx.Response(200, json={}))
    assert source.availability() == Availability(True)


@pytest.mark.parametrize("status", [401, 500])
@pytest.mark.parametrize(ARGS, SOURCES)
def test_availability_false_on_error_status(make, body, source_id, source_type, status):
    source = make(lambda request: httpx.Response(status, json={}))
    availability = source.availability()
    assert availability.available is False
    assert str(status) in availability.detail


@pytest.mark.parametrize(ARGS, SOURCES)
def test_availability_false_when_unreachable(make, body, source_id, source_type):
    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    availability = make(handler).availability()
    assert availability.available is False
    assert "ConnectError" in availability.detail


def test_omniroute_availability_probes_model_list():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json={"data": []})

    make_omniroute(handler).availability()
    assert seen == {
        "method": "GET",
        "url": f"{OMNI_BASE}/models",
        "auth": "Bearer secret-key",
    }


def test_local_availability_probes_tags():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"models": []})

    make_local(handler).availability()
    assert seen == {"method": "GET", "url": f"{LOCAL_BASE}/api/tags"}


def test_omniroute_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:20128/v1/")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    source = OmniRouteSource.from_env()
    assert source.base_url == "http://localhost:20128/v1"
    assert source.api_key == "k"
    assert source.model == "m"
    assert source.id == "omniroute"


def test_local_from_env_defaults_to_ollama_port(monkeypatch):
    monkeypatch.delenv("LOCAL_BASE_URL", raising=False)
    monkeypatch.setenv("LOCAL_MODEL", "llama3")
    source = LocalModelSource.from_env()
    assert source.base_url == "http://localhost:11434"
    assert source.model == "llama3"
    assert source.id == "local"


def test_local_from_env_reads_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_BASE_URL", "http://127.0.0.1:9999/")
    monkeypatch.setenv("LOCAL_MODEL", "m")
    source = LocalModelSource.from_env()
    assert source.base_url == "http://127.0.0.1:9999"
    assert source.model == "m"
