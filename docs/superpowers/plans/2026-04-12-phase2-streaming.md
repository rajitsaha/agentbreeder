# Phase 2: Streaming — /stream SSE Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Server-Sent Events streaming endpoint to CrewAI, Google ADK, and Claude SDK server templates.

**Architecture:** Each template gains a `/stream` POST endpoint that accepts the same `InvokeRequest` body as `/invoke`, but returns `text/event-stream` SSE response. CrewAI uses `akickoff()` + asyncio.Queue; ADK forwards `Runner.run_async()` event stream; Claude uses `messages.stream()` context manager.

**Tech Stack:** FastAPI StreamingResponse, asyncio.Queue, crewai akickoff(), google.adk Runner.run_async(), anthropic AsyncAnthropic.messages.stream()

---

## Reference: LangGraph Benchmark Pattern

The LangGraph server (`engine/runtimes/templates/langgraph_server.py`) is the most feature-complete template. Key patterns to follow:

- Module-level `_agent` global, populated in `@app.on_event("startup")` — never re-create on each request
- `sys.path.insert(0, "engine/runtimes/templates")` + `importlib` import in tests (no `sys.path` hacks in production code)
- `httpx.AsyncClient` with `ASGITransport(app=srv.app)` for endpoint tests
- Inject the mock by setting `srv._agent = mock_agent` directly (bypasses startup)
- Clean up with `srv._agent = None` after each test

For `/stream` specifically there is no LangGraph precedent yet — this plan defines the pattern the other three templates must follow.

---

## Task 1: CrewAI `/stream` Endpoint

**Files:**
- Modify: `engine/runtimes/templates/crewai_server.py`
- Create: `tests/unit/test_streaming_crewai_server.py`

### Current State

`crewai_server.py` (109 lines) exposes `/invoke` and `/health`. `_run_crew` wraps the synchronous `_crew.kickoff(inputs=...)` in `asyncio.to_thread`. There is no `/stream` endpoint and no use of `akickoff()`.

### Step 1.1 — Write the failing test

- [ ] Create `tests/unit/test_streaming_crewai_server.py` with the full content below:

```python
"""Unit tests for the /stream SSE endpoint in crewai_server.py."""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------


def _import_server():
    """Import crewai_server freshly (clears any cached module)."""
    for key in list(sys.modules.keys()):
        if "crewai_server" in key:
            del sys.modules[key]
    sys.path.insert(0, "engine/runtimes/templates")
    import crewai_server as srv  # noqa: PLC0415
    return srv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step_output(description: str = "task done", result: str = "ok") -> MagicMock:
    """Build a CrewAI-style StepOutput mock."""
    step = MagicMock()
    step.task = MagicMock()
    step.task.description = description
    step.result = result
    return step


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrewAIStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_returns_200_with_event_stream_content_type(self):
        """GET /stream must return 200 with text/event-stream content-type."""
        srv = _import_server()

        # Build a fake crew whose akickoff() sends one step then finishes
        async def fake_akickoff(inputs, callbacks=None, step_callback=None, **kwargs):
            if step_callback:
                step_callback(_make_step_output("do the thing", "result_1"))
            return MagicMock(raw="final answer")

        mock_crew = MagicMock()
        mock_crew.akickoff = fake_akickoff
        srv._crew = mock_crew

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/stream",
                json={"input": {"topic": "AI"}, "config": None},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        srv._crew = None

    @pytest.mark.asyncio
    async def test_stream_emits_step_events_for_each_step_callback(self):
        """Each step_callback invocation must produce a data: ... SSE line."""
        srv = _import_server()

        steps = [
            _make_step_output("step A", "res_a"),
            _make_step_output("step B", "res_b"),
        ]

        async def fake_akickoff(inputs, callbacks=None, step_callback=None, **kwargs):
            for s in steps:
                if step_callback:
                    step_callback(s)
                await asyncio.sleep(0)  # yield to event loop
            return MagicMock(raw="done")

        mock_crew = MagicMock()
        mock_crew.akickoff = fake_akickoff
        srv._crew = mock_crew

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": {"topic": "AI"}})

        body = response.text
        # Expect two step events
        assert body.count("event: step") == 2
        assert "step A" in body
        assert "step B" in body
        srv._crew = None

    @pytest.mark.asyncio
    async def test_stream_emits_done_event_at_end(self):
        """The final SSE event must be data: [DONE]."""
        srv = _import_server()

        async def fake_akickoff(inputs, callbacks=None, step_callback=None, **kwargs):
            return MagicMock(raw="finished")

        mock_crew = MagicMock()
        mock_crew.akickoff = fake_akickoff
        srv._crew = mock_crew

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": {}})

        assert "data: [DONE]" in response.text
        srv._crew = None

    @pytest.mark.asyncio
    async def test_stream_emits_result_event_with_final_output(self):
        """A result event containing the crew's final .raw output must be sent."""
        srv = _import_server()

        async def fake_akickoff(inputs, callbacks=None, step_callback=None, **kwargs):
            return MagicMock(raw="the final answer")

        mock_crew = MagicMock()
        mock_crew.akickoff = fake_akickoff
        srv._crew = mock_crew

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": {}})

        body = response.text
        assert "event: result" in body
        assert "the final answer" in body
        srv._crew = None

    @pytest.mark.asyncio
    async def test_stream_returns_503_when_crew_not_loaded(self):
        """/stream must return 503 when the crew has not been loaded yet."""
        srv = _import_server()
        srv._crew = None

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": {}})

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_falls_back_when_akickoff_not_available(self):
        """If the crew has no akickoff, /stream must still succeed via thread-wrapped kickoff."""
        srv = _import_server()

        # A crew with only sync kickoff (old CrewAI API)
        mock_crew = MagicMock(spec=["kickoff"])
        mock_crew.kickoff.return_value = MagicMock(raw="sync result")
        srv._crew = mock_crew

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": {"q": "test"}})

        assert response.status_code == 200
        assert "data: [DONE]" in response.text
        srv._crew = None
```

### Step 1.2 — Confirm the test fails

- [ ] Run: `pytest tests/unit/test_streaming_crewai_server.py -v 2>&1 | head -40`
- [ ] Expected output (tests fail with `404 != 200` or `AttributeError: module has no attribute 'stream'`):
  ```
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_returns_200_with_event_stream_content_type
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_step_events_for_each_step_callback
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_done_event_at_end
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_result_event_with_final_output
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_returns_503_when_crew_not_loaded
  FAILED tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_falls_back_when_akickoff_not_available
  6 failed, 0 passed
  ```

### Step 1.3 — Implement `/stream` in `crewai_server.py`

- [ ] Add the following imports at the top of `engine/runtimes/templates/crewai_server.py` (after existing imports):

```python
import json
from fastapi.responses import StreamingResponse
```

- [ ] Add the `/stream` endpoint and its generator helper **after** the `invoke` function (after line 99), before `_run_crew`:

```python
@app.post("/stream")
async def stream(request: InvokeRequest) -> StreamingResponse:
    """Stream CrewAI execution as Server-Sent Events.

    Each agent step is forwarded as an SSE ``step`` event containing a JSON
    object with ``task`` and ``result`` keys.  When the crew finishes, a
    ``result`` event is sent with the final output, followed by a terminal
    ``data: [DONE]`` line.
    """
    if _crew is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Crew not loaded yet")

    return StreamingResponse(
        _stream_crew(request.input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_crew(input_data: dict[str, Any]) -> Any:
    """Async generator that yields SSE-formatted strings for each CrewAI step."""
    queue: asyncio.Queue = asyncio.Queue()

    def _step_callback(step_output: Any) -> None:
        """Called by CrewAI on each completed step; puts event onto the queue."""
        payload: dict[str, Any] = {}
        if hasattr(step_output, "task") and hasattr(step_output.task, "description"):
            payload["task"] = step_output.task.description
        if hasattr(step_output, "result"):
            payload["result"] = str(step_output.result)
        queue.put_nowait(("step", payload))

    # Sentinel value used to signal that akickoff() has returned.
    _DONE = object()

    async def _run() -> None:
        try:
            if hasattr(_crew, "akickoff"):
                result = await _crew.akickoff(
                    inputs=input_data,
                    step_callback=_step_callback,
                )
            elif hasattr(_crew, "kickoff"):
                result = await asyncio.to_thread(_crew.kickoff, inputs=input_data)
            else:
                msg = "Crew object does not have akickoff or kickoff method"
                raise TypeError(msg)
            final_raw = getattr(result, "raw", str(result))
            queue.put_nowait(("result", {"output": final_raw}))
        except Exception as exc:  # noqa: BLE001
            queue.put_nowait(("error", {"detail": str(exc)}))
        finally:
            queue.put_nowait(_DONE)

    task = asyncio.create_task(_run())

    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            event_type, payload = item
            yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

### Step 1.4 — Confirm tests pass

- [ ] Run: `pytest tests/unit/test_streaming_crewai_server.py -v`
- [ ] Expected output:
  ```
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_returns_200_with_event_stream_content_type PASSED
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_step_events_for_each_step_callback PASSED
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_done_event_at_end PASSED
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_emits_result_event_with_final_output PASSED
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_returns_503_when_crew_not_loaded PASSED
  tests/unit/test_streaming_crewai_server.py::TestCrewAIStreamEndpoint::test_stream_falls_back_when_akickoff_not_available PASSED
  6 passed in 0.XXs
  ```

### Step 1.5 — Confirm existing CrewAI server tests still pass

- [ ] Run: `pytest tests/unit/test_runtime_crewai.py -v`
- [ ] All previously-passing tests must still pass.

### Step 1.6 — Commit

- [ ] Run: `git add engine/runtimes/templates/crewai_server.py tests/unit/test_streaming_crewai_server.py`
- [ ] Commit with message: `feat(crewai): add /stream SSE endpoint using akickoff() + asyncio.Queue`

---

## Task 2: Google ADK `/stream` Endpoint

**Files:**
- Modify: `engine/runtimes/templates/google_adk_server.py`
- Create: `tests/unit/test_streaming_adk_server.py`

### Current State

`google_adk_server.py` (150 lines) exposes `/invoke` and `/health`. `_run_agent` creates a **fresh** `Runner` and `InMemorySessionService` per request (BUG-1 documented in issue #45 — not in scope here, but the `/stream` implementation must use the module-level `_runner` correctly). `Runner.run_async()` already yields `Event` objects asynchronously — the `/stream` endpoint just needs to forward each event as SSE JSON.

### Step 2.1 — Write the failing test

- [ ] Create `tests/unit/test_streaming_adk_server.py` with the full content below:

```python
"""Unit tests for the /stream SSE endpoint in google_adk_server.py."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------


def _import_server():
    """Import google_adk_server freshly (clears any cached module)."""
    for key in list(sys.modules.keys()):
        if "google_adk_server" in key:
            del sys.modules[key]

    # Stub google.adk imports so the module loads without the real SDK installed.
    fake_google = types.ModuleType("google")
    fake_adk = types.ModuleType("google.adk")
    fake_runners = types.ModuleType("google.adk.runners")
    fake_sessions = types.ModuleType("google.adk.sessions")
    fake_genai = types.ModuleType("google.genai")
    fake_genai_types = types.ModuleType("google.genai.types")

    fake_runners.Runner = MagicMock(name="Runner")
    fake_sessions.InMemorySessionService = MagicMock(name="InMemorySessionService")
    fake_genai_types.Content = MagicMock(name="Content")
    fake_genai_types.Part = MagicMock(name="Part")

    sys.modules.setdefault("google", fake_google)
    sys.modules["google.adk"] = fake_adk
    sys.modules["google.adk.runners"] = fake_runners
    sys.modules["google.adk.sessions"] = fake_sessions
    sys.modules["google.genai"] = fake_genai
    sys.modules["google.genai.types"] = fake_genai_types

    sys.path.insert(0, "engine/runtimes/templates")
    import google_adk_server as srv  # noqa: PLC0415
    return srv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adk_event(*, is_final: bool = False, text: str | None = None) -> MagicMock:
    """Create a mock Google ADK Event object."""
    event = MagicMock()
    event.is_final_response.return_value = is_final
    if text is not None:
        part = MagicMock()
        part.text = text
        event.content = MagicMock()
        event.content.parts = [part]
    else:
        event.content = None
    # Provide a JSON-serialisable dict for the SSE payload
    event_dict = {"is_final": is_final, "text": text}
    event.model_dump = MagicMock(return_value=event_dict)
    return event


async def _aiter(*items):
    """Async generator that yields each item."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestADKStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_returns_200_with_event_stream_content_type(self):
        """/stream must return 200 with text/event-stream content-type."""
        srv = _import_server()

        srv._agent = MagicMock(name="agent")
        mock_runner = MagicMock(name="runner")
        events = [
            _make_adk_event(text="hello"),
            _make_adk_event(is_final=True, text="world"),
        ]
        mock_runner.run_async = MagicMock(
            return_value=_aiter(*events)
        )
        srv._runner = mock_runner

        # Stub session service
        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with patch.dict(
            sys.modules,
            {
                "google.adk.sessions": types.SimpleNamespace(
                    InMemorySessionService=MagicMock(return_value=mock_session_service)
                ),
                "google.genai.types": types.SimpleNamespace(
                    Content=MagicMock(return_value=MagicMock()),
                    Part=MagicMock(return_value=MagicMock()),
                ),
            },
        ):
            transport = ASGITransport(app=srv.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/stream",
                    json={"input": "hello world", "config": None},
                )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        srv._agent = None
        srv._runner = None

    @pytest.mark.asyncio
    async def test_stream_emits_one_sse_event_per_adk_event(self):
        """Every ADK Event from run_async() must map to one SSE data line."""
        srv = _import_server()

        srv._agent = MagicMock(name="agent")
        mock_runner = MagicMock(name="runner")

        intermediate = _make_adk_event(text="thinking...")
        final_ev = _make_adk_event(is_final=True, text="answer")
        mock_runner.run_async = MagicMock(return_value=_aiter(intermediate, final_ev))
        srv._runner = mock_runner

        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-abc"
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with patch.dict(
            sys.modules,
            {
                "google.adk.sessions": types.SimpleNamespace(
                    InMemorySessionService=MagicMock(return_value=mock_session_service)
                ),
                "google.genai.types": types.SimpleNamespace(
                    Content=MagicMock(return_value=MagicMock()),
                    Part=MagicMock(return_value=MagicMock()),
                ),
            },
        ):
            transport = ASGITransport(app=srv.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/stream", json={"input": "go"})

        # 2 ADK events + 1 DONE terminator
        body = response.text
        assert body.count("data:") == 3  # 2 events + [DONE]
        srv._agent = None
        srv._runner = None

    @pytest.mark.asyncio
    async def test_stream_emits_done_at_end(self):
        """The final SSE line must be data: [DONE]."""
        srv = _import_server()

        srv._agent = MagicMock(name="agent")
        mock_runner = MagicMock(name="runner")
        mock_runner.run_async = MagicMock(
            return_value=_aiter(_make_adk_event(is_final=True, text="done"))
        )
        srv._runner = mock_runner

        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-done"
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with patch.dict(
            sys.modules,
            {
                "google.adk.sessions": types.SimpleNamespace(
                    InMemorySessionService=MagicMock(return_value=mock_session_service)
                ),
                "google.genai.types": types.SimpleNamespace(
                    Content=MagicMock(return_value=MagicMock()),
                    Part=MagicMock(return_value=MagicMock()),
                ),
            },
        ):
            transport = ASGITransport(app=srv.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/stream", json={"input": "hi"})

        assert response.text.rstrip().endswith("data: [DONE]")
        srv._agent = None
        srv._runner = None

    @pytest.mark.asyncio
    async def test_stream_returns_503_when_agent_not_loaded(self):
        """/stream returns 503 when startup has not completed."""
        srv = _import_server()
        srv._agent = None
        srv._runner = None

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hello"})

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_event_payload_is_valid_json(self):
        """Each SSE data line (except [DONE]) must be valid JSON."""
        srv = _import_server()

        srv._agent = MagicMock(name="agent")
        mock_runner = MagicMock(name="runner")
        ev = _make_adk_event(text="hi", is_final=True)
        mock_runner.run_async = MagicMock(return_value=_aiter(ev))
        srv._runner = mock_runner

        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-json"
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with patch.dict(
            sys.modules,
            {
                "google.adk.sessions": types.SimpleNamespace(
                    InMemorySessionService=MagicMock(return_value=mock_session_service)
                ),
                "google.genai.types": types.SimpleNamespace(
                    Content=MagicMock(return_value=MagicMock()),
                    Part=MagicMock(return_value=MagicMock()),
                ),
            },
        ):
            transport = ASGITransport(app=srv.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/stream", json={"input": "hi"})

        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload != "[DONE]":
                    json.loads(payload)  # must not raise

        srv._agent = None
        srv._runner = None
```

### Step 2.2 — Confirm the test fails

- [ ] Run: `pytest tests/unit/test_streaming_adk_server.py -v 2>&1 | head -40`
- [ ] Expected output (all 5 tests fail with 404 or AttributeError):
  ```
  FAILED tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_returns_200_with_event_stream_content_type
  FAILED tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_emits_one_sse_event_per_adk_event
  FAILED tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_emits_done_at_end
  FAILED tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_returns_503_when_agent_not_loaded
  FAILED tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_event_payload_is_valid_json
  5 failed, 0 passed
  ```

### Step 2.3 — Implement `/stream` in `google_adk_server.py`

- [ ] Add the following import at the top of `engine/runtimes/templates/google_adk_server.py` (after existing imports):

```python
import json
from fastapi.responses import StreamingResponse
```

- [ ] Add the `/stream` endpoint and its generator helper **after** the `invoke` function (after line 111), before `_run_agent`:

```python
@app.post("/stream")
async def stream(request: InvokeRequest) -> StreamingResponse:
    """Stream Google ADK execution as Server-Sent Events.

    ``Runner.run_async()`` is an async generator that yields ADK ``Event``
    objects.  Each event is serialised to JSON and forwarded as an SSE
    ``data:`` line.  A terminal ``data: [DONE]`` line is sent after the final
    event.
    """
    if _agent is None or _runner is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    return StreamingResponse(
        _stream_agent(request.input, request.config or {}),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_agent(input_text: str, config: dict[str, Any]) -> Any:
    """Async generator that forwards each ADK Event as an SSE data line."""
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    session_service = InMemorySessionService()
    app_name = os.getenv("GOOGLE_CLOUD_PROJECT", "agentbreeder-local")
    user_id = config.get("user_id", "agentbreeder-user")
    session = await session_service.create_session(app_name=app_name, user_id=user_id)

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=input_text)],
    )

    try:
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=user_message,
        ):
            # Serialise the event to a plain dict.  ADK Events expose
            # model_dump() via Pydantic; fall back to a minimal dict.
            if hasattr(event, "model_dump"):
                payload = event.model_dump()
            else:
                payload = {
                    "is_final": bool(
                        hasattr(event, "is_final_response")
                        and event.is_final_response()
                    )
                }
                if event.content and event.content.parts:
                    payload["text"] = "".join(
                        getattr(p, "text", "") for p in event.content.parts
                    )
            yield f"data: {json.dumps(payload)}\n\n"
    except Exception as exc:  # noqa: BLE001
        error_payload = {"error": str(exc)}
        yield f"data: {json.dumps(error_payload)}\n\n"

    yield "data: [DONE]\n\n"
```

### Step 2.4 — Confirm tests pass

- [ ] Run: `pytest tests/unit/test_streaming_adk_server.py -v`
- [ ] Expected output:
  ```
  tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_returns_200_with_event_stream_content_type PASSED
  tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_emits_one_sse_event_per_adk_event PASSED
  tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_emits_done_at_end PASSED
  tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_returns_503_when_agent_not_loaded PASSED
  tests/unit/test_streaming_adk_server.py::TestADKStreamEndpoint::test_stream_event_payload_is_valid_json PASSED
  5 passed in 0.XXs
  ```

### Step 2.5 — Confirm existing ADK tests still pass

- [ ] Run: `pytest tests/unit/test_runtime_google_adk.py -v`
- [ ] All previously-passing tests must still pass.

### Step 2.6 — Commit

- [ ] Run: `git add engine/runtimes/templates/google_adk_server.py tests/unit/test_streaming_adk_server.py`
- [ ] Commit with message: `feat(google-adk): add /stream SSE endpoint forwarding Runner.run_async() events`

---

## Task 3: Claude SDK `/stream` Endpoint

**Files:**
- Modify: `engine/runtimes/templates/claude_sdk_server.py`
- Create: `tests/unit/test_streaming_claude_server.py`

### Current State

`claude_sdk_server.py` (162 lines) exposes `/invoke` and `/health`. `_run_agent` dispatches on the type of `_agent` (AsyncAnthropic, Anthropic sync, async callable, or object with `run()`). The `/stream` endpoint must handle only the `AsyncAnthropic` case using `client.messages.stream()` context manager and fall back to a non-streaming invoke wrapped in a single event for all other agent types. Note: `max_tokens` is currently hardcoded to `1024` (BUG-2 from issue #45) — the streaming path must honour the `AGENT_MAX_TOKENS` env var with a fallback to `1024`.

### Step 3.1 — Write the failing test

- [ ] Create `tests/unit/test_streaming_claude_server.py` with the full content below:

```python
"""Unit tests for the /stream SSE endpoint in claude_sdk_server.py."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------


def _import_server():
    """Import claude_sdk_server freshly (clears any cached module)."""
    for key in list(sys.modules.keys()):
        if "claude_sdk_server" in key:
            del sys.modules[key]

    # Stub the anthropic package so the module loads without it installed.
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.AsyncAnthropic = type("AsyncAnthropic", (), {})  # type: ignore[attr-defined]
    fake_anthropic.Anthropic = type("Anthropic", (), {})  # type: ignore[attr-defined]
    sys.modules["anthropic"] = fake_anthropic

    sys.path.insert(0, "engine/runtimes/templates")
    import claude_sdk_server as srv  # noqa: PLC0415
    return srv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream_event(event_type: str, text: str = "") -> MagicMock:
    """Build a mock anthropic MessageStreamEvent."""
    event = MagicMock()
    event.type = event_type
    if event_type == "content_block_delta":
        event.delta = MagicMock()
        event.delta.type = "text_delta"
        event.delta.text = text
    return event


class _FakeAsyncStream:
    """Minimal context manager that mimics anthropic AsyncMessageStream."""

    def __init__(self, events):
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def __aiter__(self):
        for event in self._events:
            yield event


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClaudeStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_returns_200_with_event_stream_content_type(self):
        """/stream must return 200 with text/event-stream content-type."""
        srv = _import_server()

        # Build a fake AsyncAnthropic client whose messages.stream() yields events
        stream_events = [
            _make_stream_event("message_start"),
            _make_stream_event("content_block_delta", "Hello"),
            _make_stream_event("message_stop"),
        ]
        mock_client = MagicMock(spec=["messages"])
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(
            return_value=_FakeAsyncStream(stream_events)
        )

        import anthropic
        mock_client.__class__ = anthropic.AsyncAnthropic
        srv._agent = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/stream",
                json={"input": "Hello Claude", "config": None},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        srv._agent = None

    @pytest.mark.asyncio
    async def test_stream_emits_one_sse_event_per_stream_event(self):
        """Each MessageStreamEvent must map to one SSE data line."""
        srv = _import_server()

        stream_events = [
            _make_stream_event("message_start"),
            _make_stream_event("content_block_delta", "part1"),
            _make_stream_event("content_block_delta", "part2"),
            _make_stream_event("message_stop"),
        ]
        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(
            return_value=_FakeAsyncStream(stream_events)
        )

        import anthropic
        mock_client.__class__ = anthropic.AsyncAnthropic
        srv._agent = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})

        # 4 stream events + 1 [DONE]
        data_lines = [
            line for line in response.text.splitlines() if line.startswith("data:")
        ]
        assert len(data_lines) == 5  # 4 events + [DONE]
        srv._agent = None

    @pytest.mark.asyncio
    async def test_stream_emits_done_at_end(self):
        """Terminal data: [DONE] must be the last line."""
        srv = _import_server()

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(
            return_value=_FakeAsyncStream([_make_stream_event("message_stop")])
        )

        import anthropic
        mock_client.__class__ = anthropic.AsyncAnthropic
        srv._agent = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})

        assert response.text.rstrip().endswith("data: [DONE]")
        srv._agent = None

    @pytest.mark.asyncio
    async def test_stream_returns_503_when_agent_not_loaded(self):
        """/stream returns 503 when startup has not run."""
        srv = _import_server()
        srv._agent = None

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_event_payload_is_valid_json(self):
        """Every SSE data line (except [DONE]) must be valid JSON."""
        srv = _import_server()

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(
            return_value=_FakeAsyncStream(
                [
                    _make_stream_event("content_block_delta", "hello"),
                    _make_stream_event("message_stop"),
                ]
            )
        )

        import anthropic
        mock_client.__class__ = anthropic.AsyncAnthropic
        srv._agent = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})

        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload != "[DONE]":
                    json.loads(payload)  # must not raise

        srv._agent = None

    @pytest.mark.asyncio
    async def test_stream_falls_back_for_non_async_anthropic_agent(self):
        """For non-AsyncAnthropic agents, /stream must still return 200 with [DONE]."""
        srv = _import_server()

        # Use an async callable agent
        async def my_agent(input_text: str) -> str:
            return "callable result"

        srv._agent = my_agent

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stream", json={"input": "hi"})

        assert response.status_code == 200
        assert "data: [DONE]" in response.text
        srv._agent = None

    @pytest.mark.asyncio
    async def test_stream_respects_agent_max_tokens_env(self, monkeypatch):
        """AGENT_MAX_TOKENS env var must override the 1024 default in stream path."""
        srv = _import_server()
        monkeypatch.setenv("AGENT_MAX_TOKENS", "4096")

        captured_kwargs: dict = {}

        class CapturingStream:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

            async def __aenter__(self):
                return _FakeAsyncStream([_make_stream_event("message_stop")])

            async def __aexit__(self, *args):
                pass

        mock_client = MagicMock()
        mock_client.messages = MagicMock()

        # We need stream() to be called and for us to capture kwargs,
        # so use a factory approach:
        def capturing_stream(**kwargs):
            captured_kwargs.update(kwargs)
            return _FakeAsyncStream([_make_stream_event("message_stop")])

        mock_client.messages.stream = capturing_stream

        import anthropic
        mock_client.__class__ = anthropic.AsyncAnthropic
        srv._agent = mock_client

        transport = ASGITransport(app=srv.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/stream", json={"input": "hi"})

        assert captured_kwargs.get("max_tokens") == 4096
        srv._agent = None
```

### Step 3.2 — Confirm the test fails

- [ ] Run: `pytest tests/unit/test_streaming_claude_server.py -v 2>&1 | head -50`
- [ ] Expected output (all 7 tests fail with 404 or import error):
  ```
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_returns_200_with_event_stream_content_type
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_emits_one_sse_event_per_stream_event
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_emits_done_at_end
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_returns_503_when_agent_not_loaded
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_event_payload_is_valid_json
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_falls_back_for_non_async_anthropic_agent
  FAILED tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_respects_agent_max_tokens_env
  7 failed, 0 passed
  ```

### Step 3.3 — Implement `/stream` in `claude_sdk_server.py`

- [ ] Add the following import at the top of `engine/runtimes/templates/claude_sdk_server.py` (after existing imports):

```python
import json
from fastapi.responses import StreamingResponse
```

- [ ] Add the `/stream` endpoint and its generator helper **after** the `invoke` function (after line 105), before `_run_agent`:

```python
@app.post("/stream")
async def stream(request: InvokeRequest) -> StreamingResponse:
    """Stream Claude SDK responses as Server-Sent Events.

    When ``_agent`` is an ``anthropic.AsyncAnthropic`` client, uses
    ``client.messages.stream()`` to yield each ``MessageStreamEvent`` as an
    SSE ``data:`` line.

    For all other agent types (async callable, object with run(), sync
    Anthropic client), the full response is obtained via the normal
    ``_run_agent()`` path and emitted as a single SSE event before the
    terminal ``[DONE]`` marker.
    """
    if _agent is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Agent not loaded yet")

    return StreamingResponse(
        _stream_agent(request.input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_agent(input_data: str) -> Any:
    """Async generator that yields SSE-formatted strings for Claude SDK agents."""
    import anthropic

    model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", "")
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "1024"))
    messages = [{"role": "user", "content": input_data}]

    if isinstance(_agent, anthropic.AsyncAnthropic):
        # Native streaming path: forward each MessageStreamEvent as SSE JSON.
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            async with _agent.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "model_dump"):
                        payload = event.model_dump()
                    else:
                        payload = {"type": getattr(event, "type", "unknown")}
                        if hasattr(event, "delta") and hasattr(event.delta, "text"):
                            payload["text"] = event.delta.text
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
    else:
        # Fallback path: run to completion and emit as a single result event.
        try:
            result = await _run_agent(input_data)
            yield f"data: {json.dumps({'type': 'result', 'text': result})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    yield "data: [DONE]\n\n"
```

### Step 3.4 — Confirm tests pass

- [ ] Run: `pytest tests/unit/test_streaming_claude_server.py -v`
- [ ] Expected output:
  ```
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_returns_200_with_event_stream_content_type PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_emits_one_sse_event_per_stream_event PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_emits_done_at_end PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_returns_503_when_agent_not_loaded PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_event_payload_is_valid_json PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_falls_back_for_non_async_anthropic_agent PASSED
  tests/unit/test_streaming_claude_server.py::TestClaudeStreamEndpoint::test_stream_respects_agent_max_tokens_env PASSED
  7 passed in 0.XXs
  ```

### Step 3.5 — Confirm existing Claude SDK tests still pass

- [ ] Run: `pytest tests/unit/test_runtime_claude_sdk.py -v`
- [ ] All previously-passing tests must still pass.

### Step 3.6 — Commit

- [ ] Run: `git add engine/runtimes/templates/claude_sdk_server.py tests/unit/test_streaming_claude_server.py`
- [ ] Commit with message: `feat(claude-sdk): add /stream SSE endpoint using messages.stream() context manager`

---

## Final Verification

- [ ] Run all three new test files together: `pytest tests/unit/test_streaming_crewai_server.py tests/unit/test_streaming_adk_server.py tests/unit/test_streaming_claude_server.py -v`
- [ ] All 18 tests must pass (6 + 5 + 7).
- [ ] Run the full unit test suite to confirm no regressions: `pytest tests/unit/ -x -q`
- [ ] Expected: previously-passing count is unchanged; 18 new tests added.

---

## Implementation Notes

### SSE Wire Format

Every event line follows the standard SSE format:

```
data: {"type": "...", ...}\n\n
```

The terminal marker is always:

```
data: [DONE]\n\n
```

This matches the convention used by the OpenAI API and is the same format the AgentBreeder dashboard SSE consumer will expect.

### FastAPI StreamingResponse Headers

Both `Cache-Control: no-cache` and `X-Accel-Buffering: no` are required in production. `X-Accel-Buffering: no` disables nginx proxy buffering which would otherwise hold back SSE frames until the buffer fills.

### CrewAI: `akickoff()` vs `kickoff()` Compatibility

CrewAI 0.80+ ships `akickoff()` as the native async entry point. Older or custom crews may only have sync `kickoff()`. The `/stream` implementation falls back to `asyncio.to_thread(crew.kickoff, ...)` in that case — the caller still gets a valid SSE stream, but without per-step events (just the final `result` event + `[DONE]`).

### Google ADK: Per-Request Session Service

`_run_agent()` currently creates a new `Runner` per request (BUG-1, issue #45). The `/stream` path deliberately uses the module-level `_runner` that was initialised at startup, while still creating a per-request `InMemorySessionService` + session (this matches the pattern in `_run_agent()` for isolation between concurrent requests). Full persistent-session support is tracked separately.

### Claude SDK: `AGENT_MAX_TOKENS` Environment Variable

The existing `_run_agent()` hardcodes `max_tokens=1024` (BUG-2, issue #45). The `/stream` path reads `AGENT_MAX_TOKENS` from the environment with a fallback of `1024`, unblocking users who need longer outputs without requiring a Phase 1 bug fix to be completed first. The same fix should be back-ported to `_run_agent()` as part of Phase 1.
