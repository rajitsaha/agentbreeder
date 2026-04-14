"""Unit tests for the /stream SSE endpoint in claude_sdk_server.py."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def _import_server():
    for key in list(sys.modules.keys()):
        if "claude_sdk_server" in key:
            del sys.modules[key]
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.AsyncAnthropic = type("AsyncAnthropic", (), {})
    fake_anthropic.Anthropic = type("Anthropic", (), {})
    sys.modules["anthropic"] = fake_anthropic
    sys.path.insert(0, "engine/runtimes/templates")
    import claude_sdk_server as srv  # noqa: PLC0415

    return srv


class _FakeTextStream:
    """Async context manager that yields text chunks via text_stream."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    @property
    def text_stream(self):
        return self._iterate()

    async def _iterate(self):
        for text in self._texts:
            yield text


class _FailStream:
    async def __aenter__(self):
        raise RuntimeError("anthropic exploded")

    async def __aexit__(self, *args):
        pass

    @property
    def text_stream(self):
        async def _gen():
            return
            yield  # make it a generator

        return _gen()


class TestClaudeStreamEndpoint:
    def _make_mock_client(self, stream_obj, srv):
        """Create a mock client whose messages.stream() returns stream_obj."""
        import anthropic

        mock_client = MagicMock()
        mock_client.__class__ = anthropic.AsyncAnthropic
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=stream_obj)
        return mock_client

    @pytest.mark.asyncio
    async def test_stream_returns_200_with_event_stream_content_type(self):
        srv = _import_server()
        stream_obj = _FakeTextStream(["Hello", " World"])
        mock_client = self._make_mock_client(stream_obj, srv)
        srv._agent = mock_client
        srv._client = mock_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "Hello Claude"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_emits_one_sse_event_per_text_chunk(self):
        srv = _import_server()
        stream_obj = _FakeTextStream(["part1", "part2", "part3"])
        mock_client = self._make_mock_client(stream_obj, srv)
        srv._agent = mock_client
        srv._client = mock_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})
        data_lines = [line for line in response.text.splitlines() if line.startswith("data:")]
        # 3 text chunks + [DONE]
        assert len(data_lines) == 4
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_emits_done_at_end(self):
        srv = _import_server()
        stream_obj = _FakeTextStream(["hi"])
        mock_client = self._make_mock_client(stream_obj, srv)
        srv._agent = mock_client
        srv._client = mock_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})
        assert response.text.rstrip().endswith("data: [DONE]")
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_returns_503_when_agent_not_loaded(self):
        srv = _import_server()
        srv._agent = None
        srv._client = None
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_event_payload_is_valid_json(self):
        srv = _import_server()
        stream_obj = _FakeTextStream(["hello"])
        mock_client = self._make_mock_client(stream_obj, srv)
        srv._agent = mock_client
        srv._client = mock_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})
        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:") :].strip()
                if payload != "[DONE]":
                    json.loads(payload)
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_falls_back_for_non_async_anthropic_agent(self):
        """When _agent is a callable (not AsyncAnthropic), stream still responds 200."""
        srv = _import_server()

        # For a non-AsyncAnthropic agent, _run_agent is called which handles callables.
        # We need _client to be non-None for the 503 check, but it won't be used for streaming.
        async def my_agent(input_text: str) -> str:
            return "callable result"

        # Create a fake client that can stream via text_stream
        stream_obj = _FakeTextStream([])
        import anthropic

        fake_client = MagicMock()
        fake_client.__class__ = anthropic.AsyncAnthropic
        fake_client.messages = MagicMock()
        fake_client.messages.stream = MagicMock(return_value=stream_obj)

        srv._agent = my_agent
        srv._client = fake_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})
        assert response.status_code == 200
        assert "data: [DONE]" in response.text
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_emits_error_event_on_exception(self):
        """If messages.stream() raises, /stream must emit an error event."""
        import anthropic as _anthropic_mod

        srv = _import_server()
        mock_client = MagicMock()
        mock_client.__class__ = _anthropic_mod.AsyncAnthropic
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=_FailStream())
        srv._agent = mock_client
        srv._client = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hello"})

        body = response.text
        assert "error" in body
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_respects_agent_max_tokens_env(self, monkeypatch):
        srv = _import_server()
        monkeypatch.setenv("AGENT_MAX_TOKENS", "4096")
        captured_kwargs: dict = {}

        def capturing_stream(**kwargs):
            captured_kwargs.update(kwargs)
            return _FakeTextStream([])

        import anthropic

        mock_client = MagicMock()
        mock_client.__class__ = anthropic.AsyncAnthropic
        mock_client.messages = MagicMock()
        mock_client.messages.stream = capturing_stream
        srv._agent = mock_client
        srv._client = mock_client
        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/stream", json={"input": "hi"})
        assert captured_kwargs.get("max_tokens") == 4096
        srv._agent = None
        srv._client = None

    @pytest.mark.asyncio
    async def test_stream_passes_tools_to_messages_stream(self):
        """_tools populated from startup must appear in messages.stream() kwargs."""
        srv = _import_server()
        import anthropic as _anthropic_mod

        mock_client = MagicMock()
        mock_client.__class__ = _anthropic_mod.AsyncAnthropic

        captured_kwargs = {}

        def _fake_stream(**kwargs):
            captured_kwargs.update(kwargs)
            return _FakeTextStream([])

        mock_client.messages = MagicMock()
        mock_client.messages.stream = _fake_stream
        srv._agent = mock_client
        srv._client = mock_client
        srv._tools = [
            {
                "name": "search",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/stream", json={"input": "hello"})

        assert "tools" in captured_kwargs
        assert captured_kwargs["tools"] == srv._tools
        srv._agent = None
        srv._client = None
        srv._tools = []
