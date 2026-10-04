"""Fallback: try sources in order until one succeeds.

FallbackSource is itself a Source, so callers keep using
``source.execute(task)`` and never see that several sources are involved.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace

from .composite import CompositeSource, attempts_from, elapsed_ms
from .contract import Result, Task
from .source import Source


class FallbackSource(CompositeSource):
    def __init__(self, sources: Sequence[Source], *, source_id: str = "fallback") -> None:
        super().__init__(sources, source_id=source_id)

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        failures: list[str] = []
        tried: list[Result] = []
        for source in self.sources:
            result = source.execute(task)
            tried.append(result)
            if result.status == "success":
                return replace(
                    result, latency_ms=elapsed_ms(start), attempts=attempts_from(tried)
                )
            failures.append(f"{source.id}: {result.error or result.status}")
        return self._all_failed(failures, start, attempts_from(tried))
