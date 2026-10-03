"""Parallel execution: start every source at once, first success wins.

ParallelSource is itself a Source, so callers keep using
``source.execute(task)``. Sources must be safe to call concurrently.
Losing sources are not interrupted: requests already in flight finish in
the background and their results are discarded.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

from .contract import Result, Task
from .source import Availability, Source, SourceType


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


class ParallelSource:
    type: SourceType = "composite"

    def __init__(self, sources: Sequence[Source], *, source_id: str = "parallel") -> None:
        if not sources:
            raise ValueError("ParallelSource needs at least one source")
        self.sources = tuple(sources)
        self.id = source_id
        self.capabilities = frozenset.intersection(*(s.capabilities for s in self.sources))

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        pool = ThreadPoolExecutor(max_workers=len(self.sources))
        futures = {pool.submit(source.execute, task): i for i, source in enumerate(self.sources)}
        failures: dict[int, str] = {}
        try:
            for future in as_completed(futures):
                result = future.result()
                if result.status == "success":
                    return replace(result, latency_ms=_elapsed_ms(start))
                failures[futures[future]] = result.error or result.status
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        detail = "; ".join(f"{self.sources[i].id}: {failures[i]}" for i in sorted(failures))
        return Result(
            content="",
            source=self.id,
            model="",
            status="error",
            latency_ms=_elapsed_ms(start),
            error="all sources failed: " + detail,
        )

    def availability(self) -> Availability:
        details: list[str] = []
        for source in self.sources:
            availability = source.availability()
            if availability.available:
                return Availability(True)
            details.append(f"{source.id}: {availability.detail or 'unavailable'}")
        return Availability(False, "; ".join(details))
