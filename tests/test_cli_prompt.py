from qs_orchestrator import cli


def test_the_default_analysis_prompt_is_not_tied_to_one_repository():
    assert "health-data" not in cli.SYSTEM
    assert "MCP" not in cli.SYSTEM
