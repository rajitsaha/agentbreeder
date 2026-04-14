"""Tests for Claude SDK eject scaffold."""

_BASE_YAML = (
    "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
)

_PROMPT_YAML = (
    "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: claude-sonnet-4-6\n"
    "prompts:\n  system: You are a helpful support agent.\n"
    "deploy:\n  cloud: aws\n"
)


def test_generate_claude_writes_agent_py(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "AsyncAnthropic" in agent_py


def test_generate_claude_uses_model(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "claude-sonnet-4-6" in agent_py


def test_generate_claude_has_tool_loop(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "tool_use" in agent_py
    assert "end_turn" in agent_py


def test_generate_claude_has_run_agent(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "async def run_agent" in agent_py


def test_generate_claude_writes_requirements(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    reqs = (tmp_path / "requirements.txt").read_text()
    assert "anthropic" in reqs


def test_generate_claude_uses_system_prompt(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_PROMPT_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "You are a helpful support agent." in agent_py


def test_generate_claude_default_system_prompt(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "You are a helpful assistant" in agent_py


def test_generate_claude_has_tools_list(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold

    _generate_claude_sdk_scaffold(_BASE_YAML, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "TOOLS" in agent_py
    assert "ToolParam" in agent_py
