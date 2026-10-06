import pytest

from qs_orchestrator.aggregate import AggregateSource
from qs_orchestrator.factory import ConfigError, build_source_from_env
from qs_orchestrator.fallback import FallbackSource
from qs_orchestrator.local import LocalModelSource
from qs_orchestrator.omniroute import OmniRouteSource
from qs_orchestrator.parallel import ParallelSource

NAMES = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_MODELS",
    "LLM_STRATEGY",
    "LOCAL_BASE_URL",
    "LOCAL_MODEL",
]
BASE = {"LLM_BASE_URL": "http://localhost:20128/v1", "LLM_API_KEY": "k"}


def _env(monkeypatch, **values):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in {**BASE, **values}.items():
        monkeypatch.setenv(name, value)


def test_from_env_can_pick_a_model_and_an_id(monkeypatch):
    _env(monkeypatch, LLM_MODEL="default")
    source = OmniRouteSource.from_env("other", source_id="omniroute:other")
    assert source.model == "other"
    assert source.id == "omniroute:other"
    assert source.base_url == "http://localhost:20128/v1"
    assert source.api_key == "k"


def test_several_models_become_separate_sources_with_distinct_ids(monkeypatch):
    _env(monkeypatch, LLM_MODELS="chatgpt-web-codex/medium,gpt-x")
    source = build_source_from_env()
    assert isinstance(source, FallbackSource)
    first, second = source.sources
    assert (first.id, first.model) == ("omniroute:chatgpt-web-codex/medium", "chatgpt-web-codex/medium")
    assert (second.id, second.model) == ("omniroute:gpt-x", "gpt-x")
    assert first.base_url == second.base_url == "http://localhost:20128/v1"


def test_model_list_is_trimmed_and_deduplicated_in_order(monkeypatch):
    _env(monkeypatch, LLM_MODELS=" a , ,b,a ,")
    source = build_source_from_env()
    assert [s.model for s in source.sources] == ["a", "b"]


def test_models_list_overrides_the_single_model_and_makes_it_optional(monkeypatch):
    _env(monkeypatch, LLM_MODELS="a,b", LLM_MODEL="ignored")
    assert [s.model for s in build_source_from_env().sources] == ["a", "b"]
    _env(monkeypatch, LLM_MODELS="a,b")
    assert [s.model for s in build_source_from_env().sources] == ["a", "b"]


def test_empty_models_list_falls_back_to_the_single_model(monkeypatch):
    _env(monkeypatch, LLM_MODELS=" , ", LLM_MODEL="m")
    source = build_source_from_env()
    assert isinstance(source, OmniRouteSource)
    assert source.id == "omniroute"
    assert source.model == "m"


def test_single_listed_model_is_not_wrapped_in_a_composite(monkeypatch):
    _env(monkeypatch, LLM_MODELS="only", LLM_STRATEGY="parallel")
    source = build_source_from_env()
    assert isinstance(source, OmniRouteSource)
    assert source.id == "omniroute:only"


def test_strategy_selects_the_composite(monkeypatch):
    for name, expected in (
        ("fallback", FallbackSource),
        ("parallel", ParallelSource),
        ("aggregate", AggregateSource),
        ("Parallel", ParallelSource),
        (" AGGREGATE ", AggregateSource),
        ("", FallbackSource),
    ):
        _env(monkeypatch, LLM_MODELS="a,b", LLM_STRATEGY=name)
        assert isinstance(build_source_from_env(), expected), name


def test_default_strategy_is_fallback(monkeypatch):
    _env(monkeypatch, LLM_MODELS="a,b")
    assert isinstance(build_source_from_env(), FallbackSource)


def test_unknown_strategy_is_a_config_error_even_with_one_source(monkeypatch):
    _env(monkeypatch, LLM_MODEL="m", LLM_STRATEGY="roundrobin")
    with pytest.raises(ConfigError) as info:
        build_source_from_env()
    message = str(info.value)
    assert "LLM_STRATEGY" in message
    assert "fallback, parallel, aggregate" in message
    assert "roundrobin" in message
    assert isinstance(info.value, ValueError)


def test_local_model_joins_the_chosen_strategy_as_the_last_source(monkeypatch):
    _env(monkeypatch, LLM_MODELS="a,b", LOCAL_MODEL="llama3", LLM_STRATEGY="parallel")
    source = build_source_from_env()
    assert isinstance(source, ParallelSource)
    assert [type(s) for s in source.sources] == [OmniRouteSource, OmniRouteSource, LocalModelSource]
    assert source.sources[2].model == "llama3"


def test_missing_credentials_are_reported_by_name_with_a_model_list(monkeypatch):
    _env(monkeypatch, LLM_MODELS="a,b")
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(KeyError) as info:
        build_source_from_env()
    assert info.value.args[0] == "LLM_API_KEY"


def test_single_model_still_requires_llm_model(monkeypatch):
    _env(monkeypatch)
    with pytest.raises(KeyError) as info:
        build_source_from_env()
    assert info.value.args[0] == "LLM_MODEL"
