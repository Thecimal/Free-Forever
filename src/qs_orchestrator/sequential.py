"""Sequential workflows: run steps in order, each building on the previous answer.

SequentialSource is itself a Source, so callers keep using
``source.execute(task)``. Each step pairs a source with a builder that turns the
original task and the previous step's Result into the Task for that step. The last
step's Result is returned; if any step fails the workflow stops there and reports
which step failed.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from .composite import CompositeSource, attempts_from, elapsed_ms
from .contract import Result, Task
from .source import Availability, Source

StepBuilder = Callable[[Task, Result | None], Task]

_PLACEHOLDER = re.compile(r"\{(input|previous)\}")


def template(text: str, *, system: str | None = None) -> StepBuilder:
    """A step builder that fills ``{input}`` and ``{previous}`` in a prompt template.

    ``{input}`` is the original task's prompt and ``{previous}`` is the previous
    step's answer (empty for the first step). Both are filled in a single pass, so
    placeholder-like text inside either value is left alone, and other braces in the
    template are untouched. The step keeps the original context, and the original
    system prompt unless ``system`` is given.
    """

    def build(original: Task, previous: Result | None) -> Task:
        values = {"input": original.prompt, "previous": previous.content if previous else ""}
        return Task(
            prompt=_PLACEHOLDER.sub(lambda match: values[match.group(1)], text),
            context=list(original.context),
            system=system if system is not None else original.system,
        )

    return build


@dataclass(frozen=True)
class Step:
    source: Source
    build: StepBuilder


class SequentialSource(CompositeSource):
    def __init__(self, steps: Sequence[Step], *, source_id: str = "sequential") -> None:
        super().__init__([step.source for step in steps], source_id=source_id)
        self.steps = tuple(steps)

    def execute(self, task: Task) -> Result:
        start = time.perf_counter()
        results: list[Result] = []
        previous: Result | None = None
        for number, step in enumerate(self.steps, start=1):
            result = step.source.execute(step.build(task, previous))
            results.append(result)
            if result.status != "success":
                return Result(
                    content="",
                    source=self.id,
                    model="",
                    status="error",
                    latency_ms=elapsed_ms(start),
                    error=(
                        f"step {number} of {len(self.steps)} ({step.source.id}) failed: "
                        f"{result.error or result.status}"
                    ),
                    attempts=attempts_from(results),
                )
            previous = result
        return replace(result, latency_ms=elapsed_ms(start), attempts=attempts_from(results))

    def availability(self) -> Availability:
        problems: list[str] = []
        for source in self.sources:
            availability = source.availability()
            if not availability.available:
                problems.append(f"{source.id}: {availability.detail or 'unavailable'}")
        if problems:
            return Availability(False, "; ".join(problems))
        return Availability(True)
