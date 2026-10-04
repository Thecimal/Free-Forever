import json

import httpx

from qs_orchestrator.contract import Task
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import build_messages


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _capture(make, response_json):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=response_json)

    make(_client(handler)).execute(Task(prompt="the prompt", system="the system"))
    return seen["body"]


def _omniroute(client):
    return OmniRouteSource("http://omniroute.test/v1", "k", "configured", client=client)


def _local(client):
    return LocalModelSource("http://local.test", "configured", client=client)


def test_task_has_no_system_prompt_by_default():
    assert Task(prompt="p").system is None


def test_build_messages_puts_the_system_message_first():
    task = Task(prompt="p", context=["c1", "c2"], system="s")
    assert build_messages(task) == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "c1\n\nc2\n\np"},
    ]


def test_build_messages_without_system_is_just_the_user_message():
    assert build_messages(Task(prompt="p")) == [{"role": "user", "content": "p"}]


def test_empty_system_is_treated_as_no_system():
    assert build_messages(Task(prompt="p", system="")) == [{"role": "user", "content": "p"}]


def test_omniroute_request_body_matches_the_old_llm_complete_request():
    body = _capture(_omniroute, {"choices": [{"message": {"content": "x"}}]})
    assert body == {
        "model": "configured",
        "messages": [
            {"role": "system", "content": "the system"},
            {"role": "user", "content": "the prompt"},
        ],
        "temperature": 0.2,
    }


def test_local_request_includes_the_system_message():
    body = _capture(_local, {"message": {"content": "x"}})
    assert body["messages"] == [
        {"role": "system", "content": "the system"},
        {"role": "user", "content": "the prompt"},
    ]
