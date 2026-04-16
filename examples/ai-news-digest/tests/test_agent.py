"""Integration and structural tests for the AI news digest agent."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent


def _agentbreeder_cmd() -> str:
    """Return the agentbreeder executable path, checking PATH and the Python bin dir."""
    found = shutil.which("agentbreeder")
    if found:
        return found
    # Check the directory of the real (resolved) Python interpreter
    for exe_path in (Path(sys.executable), Path(sys.executable).resolve()):
        candidate = exe_path.parent / "agentbreeder"
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "agentbreeder not found on PATH or in Python bin dir. Run: pip install -e <repo-root>"
    )


def test_agent_yaml_passes_agentbreeder_validate():
    """agentbreeder validate must exit 0 on the agent directory."""
    result = subprocess.run(  # noqa: S603
        [_agentbreeder_cmd(), "validate", str(AGENT_DIR / "agent.yaml")],
        cwd=AGENT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"agentbreeder validate failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


def test_root_agent_exported():
    """agent.py must export a variable named root_agent."""
    sys.path.insert(0, str(AGENT_DIR))
    from agent import root_agent

    assert root_agent is not None
    assert root_agent.name == "ai_news_digest"


def test_root_agent_has_four_tools():
    """root_agent must have exactly 4 tools registered."""
    sys.path.insert(0, str(AGENT_DIR))
    from agent import root_agent

    assert len(root_agent.tools) == 4


def test_agent_yaml_model_is_ollama():
    """agent.yaml model.primary must be an ollama/ prefixed string."""
    import yaml

    config = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
    assert config["model"]["primary"].startswith("ollama/")


def test_env_example_documents_all_required_vars():
    """Every required env var must appear in .env.example."""
    env_example = (AGENT_DIR / ".env.example").read_text()
    required = ["SMTP_USER", "SMTP_PASSWORD", "RECIPIENT_EMAILS", "OLLAMA_BASE_URL"]
    for var in required:
        assert var in env_example, f"{var} missing from .env.example"
