"""Cross-model synthesis: several sources answer, then one source merges the answers."""

from __future__ import annotations

from collections.abc import Sequence

from .aggregate import AggregateSource
from .sequential import SequentialSource, Step, template
from .source import Source

DEFAULT_PROMPT = (
    "Several models answered the same question. Write the best single answer: keep what is "
    "correct and well supported, resolve disagreements, and drop duplication.\n\n"
    "Question:\n{input}\n\n"
    "Answers:\n{previous}"
)


def synthesize(
    sources: Sequence[Source],
    synthesizer: Source,
    *,
    prompt: str = DEFAULT_PROMPT,
    source_id: str = "synthesis",
) -> SequentialSource:
    """Ask every source, then have ``synthesizer`` merge their answers into one.

    The sources run concurrently as an AggregateSource; the synthesizer receives the
    labelled answers of the ones that succeeded. In ``prompt``, ``{input}`` is the
    original question and ``{previous}`` is the labelled answers (see ``template``).
    The result is the synthesizer's, with the whole trail. If every source fails, or
    the synthesizer fails, the result is an error naming the step that failed.
    """
    return SequentialSource(
        [
            Step(AggregateSource(sources), template("{input}")),
            Step(synthesizer, template(prompt)),
        ],
        source_id=source_id,
    )
