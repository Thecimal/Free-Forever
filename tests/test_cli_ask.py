import io
import sys

import pytest

from qs_orchestrator import cli
from qs_orchestrator.contract import Attempt, Result
from qs_orchestrator.factory import ConfigError

NO_PROMPT = "No prompt given: pass it as an argument or pipe it on stdin"


class Tty(io.StringIO):
    def isatty(self):
        return True


class ExplodingStdin:
    def __init__(self, tty=False):
        self._tty = tty

    def isatty(self):
        return self._tty

    def read(self):
        raise AssertionError("stdin must not be read")


class RecordingSource:
    id = "fake"
    type = "api"
    capabilities = frozenset({"text"})

    def __init__(self, result):
        self._result = result
        self.tasks = []

    def execute(self, task):
        self.tasks.append(task)
        return self._result

    def availability(self):
        raise AssertionError("not used")


def answer(content="the answer", **kwargs):
    return Result(content=content, source="omniroute", model="m1", status="success", latency_ms=42, **kwargs)


def run_ask(monkeypatch, tmp_path, build, argv=("ask", "hello"), stdin=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["qs-orchestrator", *argv])
    monkeypatch.setattr(sys, "stdin", stdin if stdin is not None else io.StringIO(""))
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "build_source_from_env", build)
    cli.main()


def never_built():
    raise AssertionError("no source should be built")


def test_ask_sends_the_prompt_and_prints_the_answer(monkeypatch, tmp_path, capsys):
    source = RecordingSource(answer())
    run_ask(monkeypatch, tmp_path, lambda: source)
    (task,) = source.tasks
    assert (task.prompt, task.system, task.context) == ("hello", None, [])
    captured = capsys.readouterr()
    assert captured.out == "the answer\n"
    assert "Answered by: omniroute (m1) in 42 ms" in captured.err


def test_ask_passes_a_system_prompt(monkeypatch, tmp_path):
    source = RecordingSource(answer())
    run_ask(monkeypatch, tmp_path, lambda: source, argv=("ask", "hi", "--system", "Be brief."))
    assert source.tasks[0].system == "Be brief."


def test_ask_trims_whitespace_around_the_prompt(monkeypatch, tmp_path):
    source = RecordingSource(answer())
    run_ask(monkeypatch, tmp_path, lambda: source, argv=("ask", "  hi  "))
    assert source.tasks[0].prompt == "hi"


def test_ask_reads_the_prompt_from_stdin_when_no_argument_is_given(monkeypatch, tmp_path):
    source = RecordingSource(answer())
    run_ask(
        monkeypatch, tmp_path, lambda: source, argv=("ask",), stdin=io.StringIO("from stdin\n")
    )
    assert source.tasks[0].prompt == "from stdin"


def test_a_dash_reads_stdin_even_on_a_terminal(monkeypatch, tmp_path):
    source = RecordingSource(answer())
    run_ask(monkeypatch, tmp_path, lambda: source, argv=("ask", "-"), stdin=Tty("typed text"))
    assert source.tasks[0].prompt == "typed text"


def test_no_argument_on_a_terminal_is_an_error_before_any_source_is_built(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as info:
        run_ask(monkeypatch, tmp_path, never_built, argv=("ask",), stdin=ExplodingStdin(tty=True))
    assert info.value.code == NO_PROMPT


def test_empty_stdin_is_an_error(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as info:
        run_ask(monkeypatch, tmp_path, never_built, argv=("ask",), stdin=io.StringIO("  \n"))
    assert info.value.code == NO_PROMPT


def test_an_empty_argument_is_an_error_and_stdin_is_not_read(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as info:
        run_ask(monkeypatch, tmp_path, never_built, argv=("ask", " "), stdin=ExplodingStdin())
    assert info.value.code == NO_PROMPT


def test_a_failed_request_exits_with_the_error_and_prints_no_answer(monkeypatch, tmp_path, capsys):
    failed = Result("", "fallback", "", "error", 9, error="all sources failed: a: boom")
    with pytest.raises(SystemExit) as info:
        run_ask(monkeypatch, tmp_path, lambda: RecordingSource(failed))
    assert info.value.code == "Request failed: all sources failed: a: boom"
    assert capsys.readouterr().out == ""


def test_failed_attempts_are_reported_even_when_the_request_succeeds(monkeypatch, tmp_path, capsys):
    attempts = (
        Attempt("omniroute", "m", "error", 1, "boom"),
        Attempt("local", "m2", "success", 5, None),
    )
    run_ask(monkeypatch, tmp_path, lambda: RecordingSource(answer(attempts=attempts)))
    err = capsys.readouterr().err
    assert "Failed: omniroute: boom" in err
    assert "Failed: local" not in err


def test_configuration_problems_are_reported_clearly(monkeypatch, tmp_path):
    def missing():
        raise KeyError("LLM_API_KEY")

    def invalid():
        raise ConfigError("bad strategy")

    with pytest.raises(SystemExit) as first:
        run_ask(monkeypatch, tmp_path, missing)
    assert first.value.code == "Missing environment variable: LLM_API_KEY"
    with pytest.raises(SystemExit) as second:
        run_ask(monkeypatch, tmp_path, invalid)
    assert second.value.code == "Invalid configuration: bad strategy"


def test_ask_writes_no_report(monkeypatch, tmp_path):
    run_ask(monkeypatch, tmp_path, lambda: RecordingSource(answer()))
    assert not (tmp_path / "reports").exists()
