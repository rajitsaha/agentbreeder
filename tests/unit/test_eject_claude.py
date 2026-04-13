"""Tests for Claude SDK eject scaffold."""
from pathlib import Path
import pytest


def test_generate_claude_writes_agent_py(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "AsyncAnthropic" in agent_py

def test_generate_claude_uses_model(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "claude-sonnet-4-6" in agent_py

def test_generate_claude_has_tool_loop(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "tool_use" in agent_py
    assert "end_turn" in agent_py

def test_generate_claude_has_run_agent(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "async def run_agent" in agent_py

def test_generate_claude_writes_requirements(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    reqs = (tmp_path / "requirements.txt").read_text()
    assert "anthropic" in reqs

def test_generate_claude_uses_system_prompt(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\nprompts:\n  system: You are a helpful support agent.\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "You are a helpful support agent." in agent_py

def test_generate_claude_default_system_prompt(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "You are a helpful assistant" in agent_py

def test_generate_claude_has_tools_list(tmp_path):
    from cli.commands.eject import _generate_claude_sdk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
    _generate_claude_sdk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "TOOLS" in agent_py
    assert "ToolParam" in agent_py
