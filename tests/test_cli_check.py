import sys

import pytest

from qs_orchestrator import cli
from qs_orchestrator.check import DEFAULT_PROMPT
from qs_orchestrator.contract import Result
from qs_orchestrator.source import Availability


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
        return Availability(True)


OK = Result(content="ok", source="fake", model="m1", status="success", latency_ms=7)
FAILED = Result(content="", source="fake", model="m1", status="error", latency_ms=7, error="boom")


def run_check(monkeypatch, tmp_path, build, argv=("check",)):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["qs-orchestrator", *argv])
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "build_source_from_env", build)
    cli.main()


def test_check_runs_the_default_prompt_and_reports(monkeypatch, tmp_path, capsys):
    source = RecordingSource(OK)
    run_check(monkeypatch, tmp_path, lambda: source)
    assert source.tasks[0].prompt == DEFAULT_PROMPT
    out = capsys.readouterr().out
    assert "Result: success" in out
    assert "Answered by: fake (m1) in 7 ms" in out


def test_check_accepts_a_custom_prompt(monkeypatch, tmp_path, capsys):
    source = RecordingSource(OK)
    run_check(monkeypatch, tmp_path, lambda: source, argv=("check", "--prompt", "say hi"))
    assert source.tasks[0].prompt == "say hi"


def test_check_exits_with_one_when_the_task_fails(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as info:
        run_check(monkeypatch, tmp_path, lambda: RecordingSource(FAILED))
    assert info.value.code == 1
    assert "Error: boom" in capsys.readouterr().out


def test_check_reports_a_missing_setting_clearly(monkeypatch, tmp_path):
    def build():
        raise KeyError("LLM_API_KEY")

    with pytest.raises(SystemExit) as info:
        run_check(monkeypatch, tmp_path, build)
    assert info.value.code == "Missing environment variable: LLM_API_KEY"


def test_check_writes_no_report(monkeypatch, tmp_path, capsys):
    run_check(monkeypatch, tmp_path, lambda: RecordingSource(OK))
    assert not (tmp_path / "reports").exists()
