"""Integration test: register an OpenAI-compatible catalog provider via CLI,
list models against it, and invoke it. All HTTP is mocked — this test must
NOT require real API keys.

Covers Track F (issue #160) acceptance: ``model.primary: nvidia/<model>``
resolves through the engine's existing model resolution path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from cli.commands.provider import provider_app
from engine.providers.catalog import reset_cache


@pytest.fixture(autouse=True)
def _isolate_user_local(tmp_path: Path):
    """Redirect USER_LOCAL_PATH so tests don't touch the real ~/.agentbreeder."""
    fake = tmp_path / "providers.local.yaml"
    with patch("engine.providers.catalog.USER_LOCAL_PATH", fake):
        reset_cache()
        yield fake
        reset_cache()


def test_provider_list_shows_builtin_catalog() -> None:
    """`provider list --json` exposes the 9 built-in presets."""
    runner = CliRunner()
    result = runner.invoke(provider_app, ["list", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    catalog_names = {entry["name"] for entry in payload["catalog"]}
    expected = {
        "nvidia",
        "openrouter",
        "moonshot",
        "groq",
        "together",
        "fireworks",
        "deepinfra",
        "cerebras",
        "hyperbolic",
    }
    assert expected.issubset(catalog_names)


def test_provider_add_catalog_creates_user_local_entry(_isolate_user_local: Path) -> None:
    """`provider add my-vllm --type openai_compatible …` writes user-local YAML."""
    runner = CliRunner()
    result = runner.invoke(
        provider_app,
        [
            "add",
            "my-vllm",
            "--type",
            "openai_compatible",
            "--base-url",
            "https://vllm.internal.test/v1",
            "--api-key-env",
            "VLLM_TEST_KEY",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert _isolate_user_local.exists()
    contents = _isolate_user_local.read_text()
    assert "my-vllm" in contents
    assert "vllm.internal.test" in contents
    assert "VLLM_TEST_KEY" in contents


def test_provider_add_catalog_then_list_includes_user_local(
    _isolate_user_local: Path,
) -> None:
    """Round-trip: add → list shows the new entry with source=user-local."""
    runner = CliRunner()
    runner.invoke(
        provider_app,
        [
            "add",
            "my-vllm",
            "--type",
            "openai_compatible",
            "--base-url",
            "https://vllm.internal.test/v1",
            "--api-key-env",
            "VLLM_TEST_KEY",
            "--json",
        ],
    )
    reset_cache()
    result = runner.invoke(provider_app, ["list", "--json"])
    import json

    payload = json.loads(result.output)
    by_name = {e["name"]: e for e in payload["catalog"]}
    assert "my-vllm" in by_name
    assert by_name["my-vllm"]["source"] == "user-local"


def test_provider_add_catalog_requires_base_url() -> None:
    runner = CliRunner()
    result = runner.invoke(
        provider_app,
        [
            "add",
            "broken",
            "--type",
            "openai_compatible",
            "--api-key-env",
            "X_KEY",
        ],
    )
    assert result.exit_code != 0


def test_provider_add_catalog_requires_api_key_env() -> None:
    runner = CliRunner()
    result = runner.invoke(
        provider_app,
        [
            "add",
            "broken",
            "--type",
            "openai_compatible",
            "--base-url",
            "https://api.broken.test/v1",
        ],
    )
    assert result.exit_code != 0


def test_provider_remove_user_local_entry(_isolate_user_local: Path) -> None:
    runner = CliRunner()
    runner.invoke(
        provider_app,
        [
            "add",
            "my-vllm",
            "--type",
            "openai_compatible",
            "--base-url",
            "https://vllm.internal.test/v1",
            "--api-key-env",
            "VLLM_TEST_KEY",
            "--json",
        ],
    )
    result = runner.invoke(provider_app, ["remove", "my-vllm", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["removed"] == "my-vllm"
    assert payload["source"] == "user-local"


def test_provider_publish_prints_snippet_and_exits_nonzero(
    _isolate_user_local: Path,
) -> None:
    """`provider publish` is gated until git integration ships — exit code 2."""
    runner = CliRunner()
    runner.invoke(
        provider_app,
        [
            "add",
            "my-vllm",
            "--type",
            "openai_compatible",
            "--base-url",
            "https://vllm.internal.test/v1",
            "--api-key-env",
            "VLLM_TEST_KEY",
            "--json",
        ],
    )
    result = runner.invoke(provider_app, ["publish", "my-vllm", "--json"])
    # Gated path returns code 2 (deferred feature)
    assert result.exit_code == 2
    import json

    payload = json.loads(result.output)
    assert payload["status"] == "not_implemented"
    assert "my-vllm" in payload["snippet"]


def test_provider_publish_unknown_name_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(provider_app, ["publish", "ghost"])
    assert result.exit_code == 1


def test_provider_test_succeeds_against_mocked_endpoint(monkeypatch) -> None:
    """`provider test nvidia` hits GET /models with the env-var api key.

    HTTP is mocked — no real network. This verifies the full plumbing from
    CLI → catalog lookup → OpenAICompatibleProvider.list_models().
    """
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-fake-key")

    mock_response = httpx.Response(
        200,
        json={
            "object": "list",
            "data": [
                {"id": "meta-llama-3.1-405b-instruct", "object": "model"},
                {"id": "mixtral-8x7b", "object": "model"},
            ],
        },
    )

    async def _fake_get(*args, **kwargs):
        return mock_response

    async def _fake_aclose():
        return None

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_fake_get)):
        with patch("httpx.AsyncClient.aclose", new=AsyncMock(side_effect=_fake_aclose)):
            runner = CliRunner()
            result = runner.invoke(provider_app, ["test", "nvidia", "--json"])
    assert result.exit_code == 0, result.output
    import json

    payload = json.loads(result.output)
    assert payload["success"] is True
    assert payload["model_count"] == 2


def test_provider_test_missing_env_var_reports_error(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(provider_app, ["test", "nvidia"])
    assert result.exit_code == 1
    assert "NVIDIA_API_KEY" in result.output


def test_catalog_api_route_returns_presets() -> None:
    """The dashboard's `GET /api/v1/providers/catalog` exposes the catalog."""
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/providers/catalog")
    assert response.status_code == 200, response.text
    payload = response.json()
    names = {entry["name"] for entry in payload["data"]}
    expected = {
        "nvidia",
        "openrouter",
        "moonshot",
        "groq",
        "together",
        "fireworks",
        "deepinfra",
        "cerebras",
        "hyperbolic",
    }
    assert expected.issubset(names)
    # Each entry exposes the fields the dashboard renders
    nvidia = next(e for e in payload["data"] if e["name"] == "nvidia")
    assert nvidia["api_key_env"] == "NVIDIA_API_KEY"
    assert nvidia["source"] == "builtin"
    assert "integrate.api.nvidia.com" in nvidia["base_url"]


def test_invoke_through_resolver_with_mocked_http(monkeypatch) -> None:
    """End-to-end-ish: resolve `nvidia/<model>` and invoke generate(), all mocked."""
    import asyncio

    from engine.providers.registry import resolve_model_ref

    monkeypatch.setenv("NVIDIA_API_KEY", "nv-fake-key")

    async def _run() -> None:
        provider = resolve_model_ref("nvidia/meta-llama-3.1-405b-instruct")
        assert provider is not None
        assert provider.name == "nvidia"

        # Mock the chat completions response
        provider._client.post = AsyncMock(  # type: ignore[attr-defined]
            return_value=httpx.Response(
                200,
                json={
                    "id": "cmpl-1",
                    "model": "meta-llama-3.1-405b-instruct",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Greetings."},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 2,
                        "total_tokens": 6,
                    },
                },
            )
        )

        result = await provider.generate(messages=[{"role": "user", "content": "Hi"}])
        assert result.content == "Greetings."
        assert result.provider == "nvidia"
        assert result.model == "meta-llama-3.1-405b-instruct"
        await provider.close()

    asyncio.run(_run())
