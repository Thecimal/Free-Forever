# QS AI Orchestrator

A local, approval-first automation scaffold for reviewing and improving
`Thecimal/quantified-self-mcp`.

## MVP scope
- Fetch and inspect the current Git repository.
- Build a compact repository context.
- Generate a daily analysis prompt.
- Call an OpenAI-compatible endpoint (e.g. a locally configured gateway).
- Save model output as a dated Markdown report.
- Never modify source code, push, or merge automatically.

The first version deliberately separates diagnosis from code execution. Patch
generation and PR creation should be added only after the analysis output is
validated.

## Requirements
- Python 3.10+
- Git
- An OpenAI-compatible endpoint and API key, if you want automated model calls.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Set `REPO_PATH` to a local clone and configure `LLM_BASE_URL`, `LLM_API_KEY`,
and `LLM_MODEL`. Keep `.env` private.

## Run
```bash
qs-orchestrator analyze
```

To only prepare a prompt without making an API request:
```bash
qs-orchestrator analyze --dry-run
```

Reports are written to `reports/`. Review them before acting. The program does
not rotate browser sessions or bypass provider usage limits.
