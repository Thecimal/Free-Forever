"""Build the Source the CLI uses from environment settings."""

from __future__ import annotations

import os

from .fallback import FallbackSource
from .local import LocalModelSource
from .omniroute import OmniRouteSource
from .source import Source


def build_source_from_env() -> Source:
    """OmniRoute from the LLM_* settings; set LOCAL_MODEL to add a local fallback.

    Raises KeyError naming the missing variable when a required setting is absent.
    """
    primary = OmniRouteSource.from_env()
    if not os.environ.get("LOCAL_MODEL"):
        return primary
    return FallbackSource([primary, LocalModelSource.from_env()])
