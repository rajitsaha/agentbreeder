"""Tests for FileStore persistence in builders API."""
import os
import pytest
from pathlib import Path


class TestFileStore:
    def test_set_and_get(self, tmp_path):
        from api.routes.builders import FileStore
        store = FileStore(base_dir=tmp_path)
        store.set("agents", "my-agent", {"name": "my-agent", "framework": "crewai"})
        result = store.get("agents", "my-agent")
        assert result is not None
        assert result["name"] == "my-agent"

    def test_get_nonexistent_returns_none(self, tmp_path):
        from api.routes.builders import FileStore
        store = FileStore(base_dir=tmp_path)
        assert store.get("agents", "nonexistent") is None

    def test_exists_true(self, tmp_path):
        from api.routes.builders import FileStore
        store = FileStore(base_dir=tmp_path)
        store.set("tools", "my-tool", {"name": "my-tool"})
        assert store.exists("tools", "my-tool") is True

    def test_exists_false(self, tmp_path):
        from api.routes.builders import FileStore
        store = FileStore(base_dir=tmp_path)
        assert store.exists("tools", "nonexistent") is False

    def test_creates_subdirectory(self, tmp_path):
        from api.routes.builders import FileStore
        store = FileStore(base_dir=tmp_path)
        store.set("prompts", "my-prompt", {"text": "hello"})
        assert (tmp_path / "prompts").is_dir()
        assert (tmp_path / "prompts" / "my-prompt.yaml").exists()

    def test_env_var_base_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUILDERS_DATA_DIR", str(tmp_path))
        from api.routes.builders import FileStore
        # Force re-init with env var
        store = FileStore()
        store.set("agents", "test", {"x": 1})
        assert (tmp_path / "agents" / "test.yaml").exists()
