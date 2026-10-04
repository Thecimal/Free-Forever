import httpx

from qs_orchestrator.check import ANSWER_PREVIEW_CHARS, DEFAULT_PROMPT, check_source
from qs_orchestrator.contract import Attempt, Result
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import Availability


def success(content="ok", **kwargs):
    return Result(
        content=content, source="fake", model="m1", status="success", latency_ms=42, **kwargs
    )


def failure(error="boom", **kwargs):
    return Result(
        content="", source="fake", model="m1", status="error", latency_ms=9, error=error, **kwargs
    )


class FakeSource:
    id = "fake"
    type = "api"
    capabilities = frozenset({"text"})

    def __init__(
        self, result=None, availability=None, execute_error=None, availability_error=None
    ):
        self._result = result
        self._availability = availability or Availability(True)
        self._execute_error = execute_error
        self._availability_error = availability_error
        self.tasks = []

    def execute(self, task):
        self.tasks.append(task)
        if self._execute_error is not None:
            raise self._execute_error
        return self._result

    def availability(self):
        if self._availability_error is not None:
            raise self._availability_error
        return self._availability


def test_success_reports_source_availability_result_and_answer(capsys):
    source = FakeSource(success("fine"))
    assert check_source(source) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Source: fake (api)",
        "Available: yes",
        "Result: success",
        "Answered by: fake (m1) in 42 ms",
        "Answer: fine",
    ]


def test_sends_the_default_prompt_without_a_system_prompt(capsys):
    source = FakeSource(success())
    check_source(source)
    (task,) = source.tasks
    assert task.prompt == DEFAULT_PROMPT
    assert task.system is None


def test_sends_a_custom_prompt(capsys):
    source = FakeSource(success())
    check_source(source, "say hi")
    assert source.tasks[0].prompt == "say hi"


def test_unavailable_probe_is_reported_but_the_task_is_still_tried(capsys):
    source = FakeSource(success(), availability=Availability(False, "HTTPStatusError: 404"))
    assert check_source(source) == 0
    out = capsys.readouterr().out
    assert "Available: no (HTTPStatusError: 404)" in out
    assert "Result: success" in out
    assert len(source.tasks) == 1


def test_failed_result_returns_one_and_shows_the_error(capsys):
    assert check_source(FakeSource(failure("boom"))) == 1
    out = capsys.readouterr().out
    assert "Result: error" in out
    assert "Error: boom" in out
    assert "Answered by" not in out


def test_attempts_trail_is_listed_with_errors(capsys):
    attempts = (
        Attempt("omniroute", "m", "error", 3, "boom"),
        Attempt("local", "m2", "success", 5, None),
    )
    assert check_source(FakeSource(success(attempts=attempts))) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-3:] == [
        "Attempts:",
        "  - omniroute (m): error in 3 ms: boom",
        "  - local (m2): success in 5 ms",
    ]


def test_failed_result_also_lists_its_attempts(capsys):
    attempts = (Attempt("a", "m", "error", 1, "bang"),)
    check_source(FakeSource(failure("all sources failed: a: bang", attempts=attempts)))
    assert "  - a (m): error in 1 ms: bang" in capsys.readouterr().out


def test_answer_is_collapsed_to_one_line_and_truncated(capsys):
    check_source(FakeSource(success("a\n\n  b")))
    assert "Answer: a b" in capsys.readouterr().out
    check_source(FakeSource(success("x" * (ANSWER_PREVIEW_CHARS + 50))))
    assert f"Answer: {'x' * ANSWER_PREVIEW_CHARS}...\n" in capsys.readouterr().out


def test_exception_from_the_probe_is_reported_and_the_task_still_runs(capsys):
    source = FakeSource(success(), availability_error=RuntimeError("no route"))
    assert check_source(source) == 0
    assert "Available: no (RuntimeError: no route)" in capsys.readouterr().out


def test_exception_from_execute_is_reported_instead_of_crashing(capsys):
    assert check_source(FakeSource(execute_error=ValueError("bad url"))) == 1
    out = capsys.readouterr().out
    assert "Result: error" in out
    assert "Error: ValueError: bad url" in out


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_real_sources_fallback_shows_which_one_answered(capsys):
    omniroute = OmniRouteSource(
        "http://omniroute.test/v1",
        "k",
        "configured",
        client=_client(lambda request: httpx.Response(500, json={"error": "down"})),
    )
    local = LocalModelSource(
        "http://local.test",
        "configured",
        client=_client(
            lambda request: httpx.Response(
                200, json={"model": "llama3", "message": {"role": "assistant", "content": "ok"}}
            )
        ),
    )
    assert check_source(FallbackSource([omniroute, local])) == 0
    out = capsys.readouterr().out
    assert "Source: fallback (composite)" in out
    assert "Available: yes" in out
    assert "Answered by: local (llama3)" in out
    assert "  - omniroute (configured): error in " in out
    assert "  - local (llama3): success in " in out


def test_the_api_key_is_never_printed(capsys):
    source = OmniRouteSource(
        "http://omniroute.test/v1",
        "SECRET-KEY",
        "configured",
        client=_client(lambda request: httpx.Response(401, json={"error": "bad key"})),
    )
    assert check_source(source) == 1
    assert "SECRET-KEY" not in capsys.readouterr().out
