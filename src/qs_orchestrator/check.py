"""Live check: send one small task through a source and report what happened."""

from __future__ import annotations

from .contract import Result, Task
from .source import Source

DEFAULT_PROMPT = "Reply with the single word: ok"
ANSWER_PREVIEW_CHARS = 200


def check_source(source: Source, prompt: str = DEFAULT_PROMPT) -> int:
    """Print availability and the outcome of one task; return 0 on success, 1 on failure.

    This is a diagnostic, so any exception from the source is reported as text
    instead of crashing. It never prints credentials.
    """
    print(f"Source: {source.id} ({source.type})")
    try:
        availability = source.availability()
    except Exception as exc:  # noqa: BLE001 - a diagnostic reports every failure as text
        print(f"Available: no ({type(exc).__name__}: {exc})")
    else:
        detail = f" ({availability.detail})" if availability.detail else ""
        print(f"Available: {'yes' if availability.available else 'no'}{detail}")
    try:
        result = source.execute(Task(prompt=prompt))
    except Exception as exc:  # noqa: BLE001 - a diagnostic reports every failure as text
        print("Result: error")
        print(f"Error: {type(exc).__name__}: {exc}")
        return 1
    if result.status != "success":
        print("Result: error")
        print(f"Error: {result.error}")
        _print_attempts(result)
        return 1
    print("Result: success")
    print(f"Answered by: {result.source} ({result.model}) in {result.latency_ms} ms")
    print(f"Answer: {_preview(result.content)}")
    _print_attempts(result)
    return 0


def _preview(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) > ANSWER_PREVIEW_CHARS:
        return flat[:ANSWER_PREVIEW_CHARS] + "..."
    return flat


def _print_attempts(result: Result) -> None:
    if not result.attempts:
        return
    print("Attempts:")
    for attempt in result.attempts:
        line = f"  - {attempt.source} ({attempt.model}): {attempt.status} in {attempt.latency_ms} ms"
        if attempt.error:
            line += f": {attempt.error}"
        print(line)
