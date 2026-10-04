"""Shared base for sources that combine other sources."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence

from .contract import Attempt, Result, Task
from .source import Availability, Source, SourceType


def elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def attempts_from(results: Iterable[Result]) -> tuple[Attempt, ...]:
    """The trail of what was tried, flattened to the sources that did the work.

    A member that is itself a composite already carries its own trail, which is
    used as is; a plain source contributes one entry describing its Result.
    """
    attempts: list[Attempt] = []
    for result in results:
        if result.attempts:
            attempts.extend(result.attempts)
        else:
            attempts.append(
                Attempt(
                    source=result.source,
                    model=result.model,
                    status=result.status,
                    latency_ms=result.latency_ms,
                    error=result.error,
                )
            )
    return tuple(attempts)


class CompositeSource(ABC):
    """A Source built from other Sources.

    Subclasses decide how members are used (``execute``). The base owns what
    every composite shares: validation, capabilities (the intersection of the
    members' capabilities), availability (any member available), and the
    standard "all sources failed" error Result.
    """

    type: SourceType = "composite"

    def __init__(self, sources: Sequence[Source], *, source_id: str) -> None:
        if not sources:
            raise ValueError(f"{type(self).__name__} needs at least one source")
        self.sources = tuple(sources)
        self.id = source_id
        self.capabilities = frozenset.intersection(*(s.capabilities for s in self.sources))

    @abstractmethod
    def execute(self, task: Task) -> Result: ...

    def availability(self) -> Availability:
        details: list[str] = []
        for source in self.sources:
            availability = source.availability()
            if availability.available:
                return Availability(True)
            details.append(f"{source.id}: {availability.detail or 'unavailable'}")
        return Availability(False, "; ".join(details))

    def _all_failed(
        self, failures: Sequence[str], start: float, attempts: tuple[Attempt, ...] = ()
    ) -> Result:
        return Result(
            content="",
            source=self.id,
            model="",
            status="error",
            latency_ms=elapsed_ms(start),
            error="all sources failed: " + "; ".join(failures),
            attempts=attempts,
        )
