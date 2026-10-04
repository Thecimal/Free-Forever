"""Core execution contract: what goes in (Task) and what comes out (Result)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["success", "error"]


@dataclass(frozen=True)
class Task:
    prompt: str
    context: list[str] = field(default_factory=list)
    system: str | None = None


@dataclass(frozen=True)
class Attempt:
    """One step of the trail a composite source followed to produce a Result."""

    source: str
    model: str
    status: Status
    latency_ms: int
    error: str | None = None


@dataclass(frozen=True)
class Result:
    content: str
    source: str
    model: str
    status: Status
    latency_ms: int
    error: str | None = None
    attempts: tuple[Attempt, ...] = ()
