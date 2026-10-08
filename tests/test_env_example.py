from pathlib import Path
from urllib.parse import urlsplit

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def _settings():
    values = {}
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name] = value
    return values


def test_the_example_base_url_is_a_valid_url():
    url = urlsplit(_settings()["LLM_BASE_URL"])
    assert url.scheme in {"http", "https"}
    assert url.hostname
    assert isinstance(url.port, int)


def test_the_example_does_not_mention_a_specific_repository():
    assert "quantified-self-mcp" not in ENV_EXAMPLE.read_text(encoding="utf-8")
