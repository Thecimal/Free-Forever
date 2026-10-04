import sys

import pytest

from qs_orchestrator import cli
from qs_orchestrator.contract import Attempt, Result


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


def success(content="# Report\n\n\n", **kwargs):
    return Result(content=content, source="omniroute", model="m1", status="success", latency_ms=42, **kwargs)


def run_cli(monkeypatch, tmp_path, build, argv=("analyze",)):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["qs-orchestrator", *argv])
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "collect_context", lambda repo, max_chars: "CONTEXT-TEXT")
    monkeypatch.setattr(cli, "build_source_from_env", build)
    monkeypatch.setenv("REPO_PATH", str(tmp_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    cli.main()


def test_analyze_sends_the_system_prompt_and_writes_the_report(monkeypatch, tmp_path, capsys):
    source = RecordingSource(success())
    run_cli(monkeypatch, tmp_path, lambda: source)
    (task,) = source.tasks
    assert task.system == cli.SYSTEM
    assert "owner/repo" in task.prompt
    assert "CONTEXT-TEXT" in task.prompt
    (report,) = (tmp_path / "reports").glob("analysis-*.md")
    assert report.read_text(encoding="utf-8") == "# Report\n"
    assert f"Saved report: reports/{report.name}" in capsys.readouterr().out


def test_analyze_says_which_source_answered_on_stderr(monkeypatch, tmp_path, capsys):
    run_cli(monkeypatch, tmp_path, lambda: RecordingSource(success()))
    assert "Answered by: omniroute (m1) in 42 ms" in capsys.readouterr().err


def test_analyze_reports_failed_attempts_even_when_it_succeeds(monkeypatch, tmp_path, capsys):
    attempts = (
        Attempt("omniroute", "m", "error", 1, "boom"),
        Attempt("local", "m2", "success", 5, None),
    )
    run_cli(monkeypatch, tmp_path, lambda: RecordingSource(success(attempts=attempts)))
    err = capsys.readouterr().err
    assert "Failed: omniroute: boom" in err
    assert "Failed: local" not in err


def test_failed_analysis_exits_with_the_error_and_writes_no_report(monkeypatch, tmp_path):
    failed = Result("", "fallback", "", "error", 9, error="all sources failed: a: boom")
    with pytest.raises(SystemExit) as info:
        run_cli(monkeypatch, tmp_path, lambda: RecordingSource(failed))
    assert info.value.code == "Analysis failed: all sources failed: a: boom"
    assert not (tmp_path / "reports").exists()


def test_missing_setting_exits_with_a_clear_message(monkeypatch, tmp_path):
    def build():
        raise KeyError("LLM_BASE_URL")

    with pytest.raises(SystemExit) as info:
        run_cli(monkeypatch, tmp_path, build)
    assert info.value.code == "Missing environment variable: LLM_BASE_URL"


def test_dry_run_prints_the_prompt_without_building_a_source(monkeypatch, tmp_path, capsys):
    def build():
        raise AssertionError("dry run must not build a source")

    run_cli(monkeypatch, tmp_path, build, argv=("analyze", "--dry-run"))
    out = capsys.readouterr().out
    assert "SYSTEM:" in out
    assert "CONTEXT-TEXT" in out
    assert not (tmp_path / "reports").exists()
