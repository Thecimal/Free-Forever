"""Parallel execution: start every source at once, first success wins.

ParallelSource is itself a Source, so callers keep using
``source.execute(task)``. Sources must be safe to call concurrently.
Losing sources are not interrupted: requests already in flight finish in
the background and their results are discarded; the attempts trail only
lists members that had finished.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

from .composite import CompositeSource, attempts_from, elapsed_ms
from .contract import Result, Task
from .source import Source


class ParallelSource(CompositeSource):
    def __init__(self, sources: Sequence[Source], *, source_id: str = "parallel") -> None:
        super().__init__(sources, source_id=source_id)

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        pool = ThreadPoolExecutor(max_workers=len(self.sources))
        futures = {pool.submit(source.execute, task): i for i, source in enumerate(self.sources)}
        failures: dict[int, str] = {}
        finished: dict[int, Result] = {}
        try:
            for future in as_completed(futures):
                result = future.result()
                finished[futures[future]] = result
                if result.status == "success":
                    return replace(
                        result,
                        latency_ms=elapsed_ms(start),
                        attempts=attempts_from(finished[i] for i in sorted(finished)),
                    )
                failures[futures[future]] = result.error or result.status
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return self._all_failed(
            [f"{self.sources[i].id}: {failures[i]}" for i in sorted(failures)],
            start,
            attempts_from(finished[i] for i in sorted(finished)),
        )
