"""The Source contract: the only thing the rest of Free-Forever depends on.

A Source is anything that can run a Task and hand back a normalized Result
(a gateway, a local model, later a browser session). Callers use
``source.execute(task)`` and never see how the model was reached.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

import httpx

from .contract import Result, Status, Task

SourceType = Literal["api", "local", "browser", "composite"]


@dataclass(frozen=True)
class Availability:
    available: bool
    detail: str | None = None


@runtime_checkable
class Source(Protocol):
    id: str
    type: SourceType
    capabilities: frozenset[str]

    def availability(self) -> Availability: ...

    def execute(self, task: Task) -> Result: ...


def render_task(task: Task) -> str:
    """Flatten a Task into the single user message text sources send."""
    return "\n\n".join([*task.context, task.prompt])


class HttpSource(ABC):
    """Shared plumbing for sources that talk to an HTTP endpoint.

    Subclasses only describe the wire format (``_complete`` and ``_probe``).
    Timing, error handling and Result construction live here, so every
    source returns the same normalized Result by construction.
    """

    type: SourceType
    capabilities: frozenset[str] = frozenset({"text"})

    def __init__(
        self,
        source_id: str,
        model: str,
        *,
        timeout: float,
        probe_timeout: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.id = source_id
        self.model = model
        self.timeout = timeout
        self.probe_timeout = probe_timeout
        self._client = client

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        try:
            content, model = self._complete(task)
            if not isinstance(content, str):
                raise TypeError("response message content is not a string")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            return self._result("", self.model, "error", start, f"{type(exc).__name__}: {exc}")
        if not isinstance(model, str) or not model:
            model = self.model
        return self._result(content, model, "success", start)

    def availability(self) -> Availability:
        try:
            self._probe()
        except httpx.HTTPError as exc:
            return Availability(False, f"{type(exc).__name__}: {exc}")
        return Availability(True)

    @abstractmethod
    def _complete(self, task: Task) -> tuple[Any, Any]:
        """Return (content, model) from the endpoint; raise on any failure."""

    @abstractmethod
    def _probe(self) -> None:
        """Return normally if the endpoint is reachable; raise otherwise."""

    def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
        timeout: float,
    ) -> httpx.Response:
        if self._client is not None:
            return self._client.request(method, url, headers=headers, json=json, timeout=timeout)
        return httpx.request(method, url, headers=headers, json=json, timeout=timeout)

    def _result(
        self, content: str, model: str, status: Status, start: float, error: str | None = None
    ) -> Result:
        latency_ms = round((time.perf_counter() - start) * 1000)
        return Result(
            content=content,
            source=self.id,
            model=model,
            status=status,
            latency_ms=latency_ms,
            error=error,
        )
