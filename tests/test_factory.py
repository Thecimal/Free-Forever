import pytest

from qs_orchestrator.factory import build_source_from_env
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.source import Source

NAMES = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_MODELS",
    "LLM_STRATEGY",
    "LOCAL_BASE_URL",
    "LOCAL_MODEL",
]


def _env(monkeypatch, **values):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


OMNI = {"LLM_BASE_URL": "http://localhost:20128/v1", "LLM_API_KEY": "k", "LLM_MODEL": "m"}


def test_omniroute_only_when_no_local_model_is_set(monkeypatch):
    _env(monkeypatch, **OMNI)
    source = build_source_from_env()
    assert isinstance(source, OmniRouteSource)
    assert isinstance(source, Source)
    assert source.id == "omniroute"


def test_empty_local_model_does_not_add_a_fallback(monkeypatch):
    _env(monkeypatch, LOCAL_MODEL="", **OMNI)
    assert isinstance(build_source_from_env(), OmniRouteSource)


def test_local_model_adds_a_local_fallback_after_omniroute(monkeypatch):
    _env(monkeypatch, LOCAL_MODEL="llama3", **OMNI)
    source = build_source_from_env()
    assert isinstance(source, FallbackSource)
    primary, secondary = source.sources
    assert isinstance(primary, OmniRouteSource)
    assert isinstance(secondary, LocalModelSource)
    assert secondary.model == "llama3"
    assert secondary.base_url == "http://localhost:11434"


def test_missing_required_setting_names_the_variable(monkeypatch):
    _env(monkeypatch, LLM_API_KEY="k", LLM_MODEL="m")
    with pytest.raises(KeyError) as info:
        build_source_from_env()
    assert info.value.args[0] == "LLM_BASE_URL"
