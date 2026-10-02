import json

import httpx
import pytest

from qs_orchestrator.contract import Result, Task
from qs_orchestrator.executor import Executor, OmniRouteExecutor

BASE = "http://omniroute.test/v1"


def make_executor(handler, model="configured-model"):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OmniRouteExecutor(BASE + "/", "secret-key", model, client=client)


def ok_body(content="hello", model="routed-model"):
    return {"model": model, "choices": [{"message": {"role": "assistant", "content": content}}]}


def test_full_path_task_to_normalized_result():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_body("X is a thing."))

    executor: Executor = make_executor(handler)
    result = executor.execute(Task(prompt="Hello, explain X", context=["doc A", "doc B"]))

    assert seen["url"] == f"{BASE}/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["model"] == "configured-model"
    assert seen["body"]["messages"] == [
        {"role": "user", "content": "doc A\n\ndoc B\n\nHello, explain X"}
    ]
    assert isinstance(result, Result)
    assert result.content == "X is a thing."
    assert result.source == "omniroute"
    assert result.model == "routed-model"
    assert result.status == "success"
    assert result.error is None
    assert isinstance(result.latency_ms, int) and result.latency_ms >= 0


def test_task_without_context_sends_prompt_only():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=ok_body())

    make_executor(handler).execute(Task(prompt="just this"))
    assert seen["body"]["messages"] == [{"role": "user", "content": "just this"}]


def test_model_falls_back_to_configured_when_response_omits_it():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    result = make_executor(handler).execute(Task(prompt="p"))
    assert result.status == "success"
    assert result.model == "configured-model"


def test_http_error_becomes_error_result():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    result = make_executor(handler).execute(Task(prompt="p"))
    assert result.status == "error"
    assert result.content == ""
    assert result.source == "omniroute"
    assert result.model == "configured-model"
    assert "500" in result.error


def test_transport_error_becomes_error_result():
    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    result = make_executor(handler).execute(Task(prompt="p"))
    assert result.status == "error"
    assert "ConnectError" in result.error


@pytest.mark.parametrize(
    "response_kwargs",
    [
        {"json": {}},
        {"json": {"choices": []}},
        {"json": {"choices": [{"message": {"content": None}}]}},
        {"content": b"not json"},
    ],
)
def test_malformed_response_becomes_error_result(response_kwargs):
    def handler(request):
        return httpx.Response(200, **response_kwargs)

    result = make_executor(handler).execute(Task(prompt="p"))
    assert result.status == "error"
    assert result.content == ""
    assert result.error


def test_from_env_reads_existing_llm_settings(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:9999/v1/")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    executor = OmniRouteExecutor.from_env()
    assert executor.base_url == "http://localhost:9999/v1"
    assert executor.api_key == "k"
    assert executor.model == "m"
