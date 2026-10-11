import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match
    return match.group(1)


def _changelog():
    return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_the_version_is_a_plain_semantic_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", _version())


def test_the_newest_changelog_release_matches_the_package_version():
    releases = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", _changelog(), re.MULTILINE)
    assert releases
    assert releases[0] == _version()


def test_unreleased_comes_before_the_newest_release():
    text = _changelog()
    assert text.index("## [Unreleased]") < text.index(f"## [{_version()}]")
