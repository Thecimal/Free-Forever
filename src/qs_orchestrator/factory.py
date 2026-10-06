"""Build the Source the CLI uses from environment settings."""

from __future__ import annotations

import os

from .aggregate import AggregateSource
from .fallback import FallbackSource
from .local import LocalModelSource
from .omniroute import OmniRouteSource
from .parallel import ParallelSource
from .source import Source

STRATEGIES = {
    "fallback": FallbackSource,
    "parallel": ParallelSource,
    "aggregate": AggregateSource,
}


class ConfigError(ValueError):
    """An environment setting has an invalid value."""


def _models_from_env() -> list[str]:
    raw = os.environ.get("LLM_MODELS", "")
    return list(dict.fromkeys(model.strip() for model in raw.split(",") if model.strip()))


def build_source_from_env() -> Source:
    """Build the source for the configured models.

    OmniRoute serves the LLM_MODELS list, or the single LLM_MODEL when the list is
    empty; each listed model is its own source. LOCAL_MODEL adds a local model as one
    more source. Several sources are combined with LLM_STRATEGY: fallback (the
    default), parallel or aggregate.

    Raises KeyError naming a missing required setting, or ConfigError for an invalid
    value.
    """
    name = os.environ.get("LLM_STRATEGY", "").strip().lower() or "fallback"
    if name not in STRATEGIES:
        raise ConfigError(f"LLM_STRATEGY must be one of {', '.join(STRATEGIES)}; got {name!r}")
    models = _models_from_env()
    sources: list[Source]
    if models:
        sources = [OmniRouteSource.from_env(model, source_id=f"omniroute:{model}") for model in models]
    else:
        sources = [OmniRouteSource.from_env()]
    if os.environ.get("LOCAL_MODEL"):
        sources.append(LocalModelSource.from_env())
    if len(sources) == 1:
        return sources[0]
    return STRATEGIES[name](sources)
