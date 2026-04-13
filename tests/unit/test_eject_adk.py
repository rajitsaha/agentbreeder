"""Tests for Google ADK eject scaffold."""
from pathlib import Path
import pytest


def test_generate_adk_writes_agent_py(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "LlmAgent" in agent_py

def test_generate_adk_uses_model_from_yaml(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "gemini-2.0-flash" in agent_py

def test_generate_adk_writes_requirements(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    reqs = (tmp_path / "requirements.txt").read_text()
    assert "google-adk" in reqs

def test_generate_adk_sequential_when_subagents(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: multi-agent\nversion: 1.0.0\nframework: google_adk\ndescription: Multi-step agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\nsubagents:\n  - name: step1\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "SequentialAgent" in agent_py

def test_generate_adk_llm_agent_when_no_subagents(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "LlmAgent" in agent_py
    assert "SequentialAgent" not in agent_py

def test_generate_adk_root_agent_exported(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: A test agent\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "root_agent" in agent_py

def test_generate_adk_uses_description(tmp_path):
    from cli.commands.eject import _generate_google_adk_scaffold
    yaml_content = "name: test-agent\nversion: 1.0.0\nframework: google_adk\ndescription: Handles customer queries\nteam: eng\nowner: a@b.com\nmodel:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
    _generate_google_adk_scaffold(yaml_content, tmp_path)
    agent_py = (tmp_path / "agent.py").read_text()
    assert "Handles customer queries" in agent_py
