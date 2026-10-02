import subprocess
from pathlib import Path

IGNORE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build"}
ALLOW_SUFFIXES = {".py", ".toml", ".md", ".yml", ".yaml", ".ini", ".cfg", ".sql"}


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], text=True,
                       capture_output=True, check=True)
    return p.stdout.strip()


def collect_context(repo: Path, max_chars: int) -> str:
    if not (repo / ".git").exists():
        raise ValueError(f"Not a Git repository: {repo}")
    parts = [
        "## Git status\n" + git(repo, "status", "--short", "--branch"),
        "## Recent commits\n" + git(repo, "log", "-8", "--oneline"),
        "## Tracked files\n" + git(repo, "ls-files"),
    ]
    tracked = git(repo, "ls-files").splitlines()
    chunks = []
    for name in tracked:
        path = Path(name)
        if path.suffix.lower() not in ALLOW_SUFFIXES:
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        full = repo / path
        if not full.is_file():
            continue
        try:
            content = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        chunks.append(f"\n### FILE: {name}\n```\n{content}\n```")
    parts.append("## Source files\n" + "\n".join(chunks))
    result = "\n\n".join(parts)
    return result[:max_chars] + ("\n[CONTEXT TRUNCATED]" if len(result) > max_chars else "")
