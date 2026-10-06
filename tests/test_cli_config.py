import sys

import pytest

from qs_orchestrator import cli
from qs_orchestrator.factory import ConfigError


def run(monkeypatch, tmp_path, argv):
    def build():
        raise ConfigError("LLM_STRATEGY must be one of fallback, parallel, aggregate; got 'x'")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["qs-orchestrator", *argv])
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "collect_context", lambda repo, max_chars: "CONTEXT")
    monkeypatch.setattr(cli, "build_source_from_env", build)
    monkeypatch.setenv("REPO_PATH", str(tmp_path))
    cli.main()


@pytest.mark.parametrize("argv", [("analyze",), ("check",)])
def test_invalid_configuration_exits_with_a_clear_message(monkeypatch, tmp_path, argv):
    with pytest.raises(SystemExit) as info:
        run(monkeypatch, tmp_path, argv)
    assert info.value.code == (
        "Invalid configuration: LLM_STRATEGY must be one of fallback, parallel, aggregate; got 'x'"
    )
    assert not (tmp_path / "reports").exists()
