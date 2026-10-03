"""Fallback: try sources in order until one succeeds.

FallbackSource is itself a Source, so callers keep using
``source.execute(task)`` and never see that several sources are involved.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace

from .contract import Result, Task
from .source import Availability, Source, SourceType


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


class FallbackSource:
    type: SourceType = "composite"

    def __init__(self, sources: Sequence[Source], *, source_id: str = "fallback") -> None:
        if not sources:
            raise ValueError("FallbackSource needs at least one source")
        self.sources = tuple(sources)
        self.id = source_id
        self.capabilities = frozenset.intersection(*(s.capabilities for s in self.sources))

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        failures: list[str] = []
        for source in self.sources:
            result = source.execute(task)
            if result.status == "success":
                return replace(result, latency_ms=_elapsed_ms(start))
            failures.append(f"{source.id}: {result.error or result.status}")
        return Result(
            content="",
            source=self.id,
            model="",
            status="error",
            latency_ms=_elapsed_ms(start),
            error="all sources failed: " + "; ".join(failures),
        )

    def availability(self) -> Availability:
        details: list[str] = []
        for source in self.sources:
            availability = source.availability()
            if availability.available:
                return Availability(True)
            details.append(f"{source.id}: {availability.detail or 'unavailable'}")
        return Availability(False, "; ".join(details))
