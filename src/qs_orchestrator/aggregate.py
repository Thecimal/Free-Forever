"""Aggregation: run every source concurrently and combine the answers.

AggregateSource is itself a Source, so callers keep using
``source.execute(task)``. It waits for every member, then returns one
Result: successful if at least one member succeeded, with each successful
answer under a header naming the source that produced it. Members' answers
appear in source order, not completion order. Sources must be safe to call
concurrently.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from .composite import CompositeSource, attempts_from, elapsed_ms
from .contract import Result, Task
from .source import Source


class AggregateSource(CompositeSource):
    def __init__(self, sources: Sequence[Source], *, source_id: str = "aggregate") -> None:
        super().__init__(sources, source_id=source_id)

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(self.sources)) as pool:
            results = list(pool.map(lambda source: source.execute(task), self.sources))
        successes = [result for result in results if result.status == "success"]
        if not successes:
            failures = [
                f"{source.id}: {result.error or result.status}"
                for source, result in zip(self.sources, results, strict=True)
            ]
            return self._all_failed(failures, start, attempts_from(results))
        return Result(
            content="\n\n".join(f"## {result.source}\n{result.content}" for result in successes),
            source=self.id,
            model=", ".join(dict.fromkeys(result.model for result in successes)),
            status="success",
            latency_ms=elapsed_ms(start),
            attempts=attempts_from(results),
        )
