"""Tests for engine/governance.py — RBAC checks."""

from __future__ import annotations

from engine.config_parser import AgentConfig, FrameworkType
from engine.governance import RBACDeniedError, check_rbac


def _make_config() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        version="1.0.0",
        team="engineering",
        owner="test@example.com",
        framework=FrameworkType.langgraph,
        model={"primary": "gpt-4o"},
        deploy={"cloud": "local"},
    )


class TestCheckRBAC:
    def test_stub_always_passes(self) -> None:
        """v0.1 RBAC stub should always pass."""
        config = _make_config()
        # Should not raise
        check_rbac(config, user="anyone")
        check_rbac(config, user="anonymous")


class TestRBACDeniedError:
    def test_error_message(self) -> None:
        error = RBACDeniedError(user="alice", team="platform", action="deploy")
        assert "alice" in str(error)
        assert "platform" in str(error)
        assert "deploy" in str(error)
        assert error.user == "alice"
        assert error.team == "platform"
        assert error.action == "deploy"
