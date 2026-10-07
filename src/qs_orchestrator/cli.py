import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .check import DEFAULT_PROMPT, check_source
from .contract import Task
from .factory import ConfigError, build_source_from_env
from .repo import collect_context

SYSTEM = """You are a senior Python/MCP engineer reviewing a health-data MCP server.
Be evidence-driven. Do not invent defects. Identify the single highest-priority
actionable pain point. Distinguish verified facts from hypotheses. Return:
# Highest-priority pain point
## Evidence (file paths and symbols)
## User impact
## Root cause
## Proposed solution
## Definition of Done
## Risks and unknowns
Do not propose unrelated cleanup. If repository context is insufficient, say so."""


def _build_source():
    try:
        return build_source_from_env()
    except KeyError as exc:
        raise SystemExit(f"Missing environment variable: {exc.args[0]}") from exc
    except ConfigError as exc:
        raise SystemExit(f"Invalid configuration: {exc}") from exc


NO_PROMPT = "No prompt given: pass it as an argument or pipe it on stdin"


def _read_prompt(argument):
    if argument is None and sys.stdin.isatty():
        raise SystemExit(NO_PROMPT)
    text = sys.stdin.read() if argument in (None, "-") else argument
    if not text.strip():
        raise SystemExit(NO_PROMPT)
    return text.strip()


def _report(result):
    for attempt in result.attempts:
        if attempt.status != "success":
            print(f"Failed: {attempt.source}: {attempt.error}", file=sys.stderr)
    print(
        f"Answered by: {result.source} ({result.model}) in {result.latency_ms} ms",
        file=sys.stderr,
    )


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(prog="qs-orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze the local repository")
    analyze.add_argument("--dry-run", action="store_true",
                         help="Print prompt without calling a model")
    check = sub.add_parser("check", help="Send one small task through the configured source")
    check.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt to send")
    ask = sub.add_parser("ask", help="Send a prompt through the configured source")
    ask.add_argument("prompt", nargs="?", help="Prompt to send (default: read from stdin)")
    ask.add_argument("--system", help="Optional system prompt")
    args = parser.parse_args()

    if args.command == "analyze":
        repo = Path(os.environ.get("REPO_PATH", ".")).expanduser().resolve()
        context = collect_context(repo, int(os.getenv("MAX_CONTEXT_CHARS", "50000")))
        prompt = f"""Repository: {os.getenv('GITHUB_REPOSITORY', 'unknown')}
Local path: {repo}

Review the following repository context and identify the highest-priority
pain point. Cite exact files/symbols from the supplied context.

{context}
"""
        if args.dry_run:
            print("SYSTEM:\n", SYSTEM, "\nUSER:\n", prompt)
            return
        source = _build_source()
        result = source.execute(Task(prompt=prompt, system=SYSTEM))
        if result.status != "success":
            raise SystemExit(f"Analysis failed: {result.error}")
        _report(result)
        reports = Path("reports")
        reports.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = reports / f"analysis-{stamp}.md"
        output.write_text(result.content.rstrip() + "\n", encoding="utf-8")
        print(f"Saved report: {output}")

    if args.command == "check":
        code = check_source(_build_source(), args.prompt)
        if code:
            raise SystemExit(code)

    if args.command == "ask":
        prompt = _read_prompt(args.prompt)
        result = _build_source().execute(Task(prompt=prompt, system=args.system))
        if result.status != "success":
            raise SystemExit(f"Request failed: {result.error}")
        print(result.content)
        _report(result)


if __name__ == "__main__":
    main()
