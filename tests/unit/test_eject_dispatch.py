"""Tests for the eject() command framework dispatch logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Minimal valid YAML for each framework
_CREWAI_YAML = (
    "name: my-agent\nversion: 1.0.0\nframework: crewai\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: gpt-4o\ndeploy:\n  cloud: aws\n"
)

_ADK_YAML = (
    "name: my-agent\nversion: 1.0.0\nframework: google_adk\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: gemini-2.0-flash\ndeploy:\n  cloud: gcp\n"
)

_CLAUDE_YAML = (
    "name: my-agent\nversion: 1.0.0\nframework: claude_sdk\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: claude-sonnet-4-6\ndeploy:\n  cloud: aws\n"
)


class TestEjectDispatch:
    """Test that eject() dispatches to the correct scaffold generator."""

    def _run_eject(self, yaml_content: str, output: str) -> None:
        """Import and invoke eject() with a mock YAML path."""
        from cli.commands.eject import eject

        with patch("builtins.open", lambda p, *a, **k: __import__("io").StringIO(yaml_content)):
            with patch("pathlib.Path.read_text", return_value=yaml_content):
                eject(agent_yaml=Path("agent.yaml"), output=output, sdk="python")

    def test_eject_crewai_calls_scaffold(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CREWAI_YAML)
        out = str(tmp_path / "out")

        with patch("cli.commands.eject._generate_crewai_scaffold") as mock_scaffold:
            eject(config_path=yaml_file, output=out, sdk="python")
            mock_scaffold.assert_called_once()

    def test_eject_google_adk_calls_scaffold(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_ADK_YAML)
        out = str(tmp_path / "out")

        with patch("cli.commands.eject._generate_google_adk_scaffold") as mock_scaffold:
            eject(config_path=yaml_file, output=out, sdk="python")
            mock_scaffold.assert_called_once()

    def test_eject_claude_sdk_calls_scaffold(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CLAUDE_YAML)
        out = str(tmp_path / "out")

        with patch("cli.commands.eject._generate_claude_sdk_scaffold") as mock_scaffold:
            eject(config_path=yaml_file, output=out, sdk="python")
            mock_scaffold.assert_called_once()

    def test_eject_crewai_scaffold_failure_exits(self, tmp_path):
        import typer

        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CREWAI_YAML)
        out = str(tmp_path / "out")

        with patch(
            "cli.commands.eject._generate_crewai_scaffold",
            side_effect=RuntimeError("scaffold failed"),
        ):
            with pytest.raises(typer.Exit):
                eject(config_path=yaml_file, output=out, sdk="python")

    def test_eject_adk_scaffold_failure_exits(self, tmp_path):
        import typer

        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_ADK_YAML)
        out = str(tmp_path / "out")

        with patch(
            "cli.commands.eject._generate_google_adk_scaffold",
            side_effect=RuntimeError("scaffold failed"),
        ):
            with pytest.raises(typer.Exit):
                eject(config_path=yaml_file, output=out, sdk="python")

    def test_eject_claude_scaffold_failure_exits(self, tmp_path):
        import typer

        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CLAUDE_YAML)
        out = str(tmp_path / "out")

        with patch(
            "cli.commands.eject._generate_claude_sdk_scaffold",
            side_effect=RuntimeError("scaffold failed"),
        ):
            with pytest.raises(typer.Exit):
                eject(config_path=yaml_file, output=out, sdk="python")

    def test_eject_crewai_writes_files(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CREWAI_YAML)
        out = str(tmp_path / "out")

        eject(config_path=yaml_file, output=out, sdk="python")
        assert (tmp_path / "out" / "crew.py").exists()

    def test_eject_adk_writes_files(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_ADK_YAML)
        out = str(tmp_path / "out")

        eject(config_path=yaml_file, output=out, sdk="python")
        assert (tmp_path / "out" / "agent.py").exists()

    def test_eject_claude_writes_files(self, tmp_path):
        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(_CLAUDE_YAML)
        out = str(tmp_path / "out")

        eject(config_path=yaml_file, output=out, sdk="python")
        assert (tmp_path / "out" / "agent.py").exists()

    def test_eject_invalid_yaml_falls_through(self, tmp_path):
        """Bad YAML falls through to legacy SDK path (not crewai/adk/claude_sdk dispatch)."""
        import typer

        from cli.commands.eject import eject

        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text("{not: valid: yaml: [}")
        out = str(tmp_path / "out")

        # framework will be "" — falls through to unsupported SDK branch
        with pytest.raises(typer.Exit):
            eject(config_path=yaml_file, output=out, sdk="unsupported_sdk")


class TestScaffoldEdgeCases:
    """Cover error-path branches in scaffold generators."""

    def test_crewai_scaffold_non_dict_yaml_raises(self, tmp_path):
        from cli.commands.eject import _generate_crewai_scaffold

        with pytest.raises((ValueError, AttributeError, TypeError)):
            _generate_crewai_scaffold("- item1\n- item2\n", tmp_path)

    def test_adk_scaffold_non_dict_yaml_raises(self, tmp_path):
        from cli.commands.eject import _generate_google_adk_scaffold

        with pytest.raises((ValueError, AttributeError, TypeError)):
            _generate_google_adk_scaffold("- item1\n- item2\n", tmp_path)

    def test_claude_scaffold_empty_system_prompt_uses_default(self, tmp_path):
        """Empty string system prompt should fall back to default."""
        from cli.commands.eject import _generate_claude_sdk_scaffold

        yaml_content = (
            "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\n"
            "description: A test agent\nteam: eng\nowner: a@b.com\n"
            "model:\n  primary: claude-sonnet-4-6\n"
            "prompts:\n  system: ''\n"  # empty string prompt
            "deploy:\n  cloud: aws\n"
        )
        _generate_claude_sdk_scaffold(yaml_content, tmp_path)
        agent_py = (tmp_path / "agent.py").read_text()
        assert "You are a helpful assistant." in agent_py

    def test_claude_scaffold_non_dict_model_uses_default(self, tmp_path):
        """Non-dict model config falls back to default model."""
        from cli.commands.eject import _generate_claude_sdk_scaffold

        yaml_content = (
            "name: test-agent\nversion: 1.0.0\nframework: claude_sdk\n"
            "description: A test agent\nteam: eng\nowner: a@b.com\n"
            "model: null\n"
            "deploy:\n  cloud: aws\n"
        )
        _generate_claude_sdk_scaffold(yaml_content, tmp_path)
        agent_py = (tmp_path / "agent.py").read_text()
        assert "claude-sonnet-4-6" in agent_py
