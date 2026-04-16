# Phase 3: Tool Bridge — Registry Tools to Framework-Native Objects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `engine/tool_bridge.py` with three adapters (CrewAI, ADK, Claude) and wire them into each server template's startup so `agent.yaml` `tools:` entries are live at runtime.

**Architecture:** Tool bridge reads `ToolRef` list from config, resolves tool endpoint URLs from `TOOL_ENDPOINT_*` env vars, and returns framework-native tool objects. Server templates import the bridge at module level and call the appropriate adapter during the `startup` event handler. Inline tools (those with `name` + `schema_`) make HTTP POST calls to a registry endpoint; `ref:` tools resolve their endpoint from `TOOL_ENDPOINT_{slugified_ref}` env vars where the ref slug is the full ref with `/` and `-` converted to `_` and uppercased (e.g., `tools/zendesk-mcp` -> `TOOL_ENDPOINT_TOOLS_ZENDESK_MCP`).

**Tech Stack:** `crewai.tools.BaseTool`, Google ADK `FunctionTool` callable pattern, `anthropic.types.ToolParam`, `httpx.AsyncClient` for tool HTTP calls

**Key source files:**
- `engine/config_parser.py` -- `ToolRef` definition (lines 52-59): `ref`, `name`, `type`, `description`, `schema_` (alias `schema`)
- `engine/runtimes/templates/crewai_server.py` -- module-level `_crew: Any = None`, startup sets it via `_load_agent()`
- `engine/runtimes/templates/claude_sdk_server.py` -- module-level `_agent: Any = None`, `_run_agent()` calls `_agent.messages.create()`
- `engine/runtimes/templates/google_adk_server.py` -- module-level `_agent: Any = None`, `_runner: Any = None`, startup creates `Runner(agent=_agent, ...)`

---

## Task 1: Create `engine/tool_bridge.py` with `to_claude_tools()`

**Why first:** No dynamic code generation, no framework dependencies beyond `anthropic` -- pure dict transformation. Establishes the module, the slug helper, and the test fixture pattern all subsequent tasks reuse.

### Steps

- [ ] 1.1 Create `engine/tool_bridge.py` with the slug helper and `to_claude_tools()`:

```python
"""AgentBreeder tool bridge -- converts ToolRef list to framework-native tool objects.

Each adapter reads TOOL_ENDPOINT_<SLUG> environment variables to locate tool HTTP
endpoints. The slug is derived from the ToolRef ref or name:
  tools/zendesk-mcp  ->  TOOL_ENDPOINT_TOOLS_ZENDESK_MCP
  order-lookup       ->  TOOL_ENDPOINT_ORDER_LOOKUP
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

# Env var prefix used for all tool endpoint URLs.
_ENV_PREFIX = "TOOL_ENDPOINT_"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ref_to_slug(ref_or_name: str) -> str:
    """Convert a tool ref or name to the env-var suffix used for endpoint lookup.

    Examples::

        tools/zendesk-mcp  ->  TOOLS_ZENDESK_MCP
        order-lookup        ->  ORDER_LOOKUP
        search              ->  SEARCH
    """
    slug = re.sub(r"[^a-zA-Z0-9]", "_", ref_or_name)
    return slug.upper()


def _resolve_endpoint(tool_ref: "ToolRef") -> str | None:  # noqa: F821
    """Return the HTTP endpoint URL for *tool_ref*, or None if not configured.

    Precedence: ref field first, then name field.
    """
    key: str | None = tool_ref.ref or tool_ref.name
    if key is None:
        return None
    env_key = _ENV_PREFIX + _ref_to_slug(key)
    return os.environ.get(env_key)


# ---------------------------------------------------------------------------
# Claude adapter
# ---------------------------------------------------------------------------


def to_claude_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of ToolRef objects to Anthropic ToolParam dicts.

    Each dict has the shape::

        {
            "name": str,
            "description": str,
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...],
            }
        }

    Tools without a resolvable name are skipped with a warning.

    Args:
        tools: List of ToolRef instances from AgentConfig.tools.

    Returns:
        List of anthropic.types.ToolParam-compatible dicts.
    """
    result: list[dict[str, Any]] = []
    for tool_ref in tools:
        # Determine a usable name: prefer explicit name, fall back to the
        # last path component of the ref (e.g. "tools/zendesk-mcp" -> "zendesk-mcp").
        name: str | None = tool_ref.name
        if name is None and tool_ref.ref is not None:
            name = tool_ref.ref.split("/")[-1]
        if name is None:
            logger.warning("Skipping ToolRef with no name or ref: %r", tool_ref)
            continue

        # Sanitise name to match Anthropic's ^[a-zA-Z0-9_-]{1,64}$ constraint.
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]

        description: str = tool_ref.description or f"Tool: {safe_name}"

        # Build input_schema from the inline schema dict, or fall back to an
        # empty object schema so the ToolParam is still valid.
        raw_schema: dict[str, Any] = tool_ref.schema_ or {}
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": raw_schema.get("properties", {}),
        }
        if "required" in raw_schema:
            input_schema["required"] = raw_schema["required"]

        result.append(
            {
                "name": safe_name,
                "description": description,
                "input_schema": input_schema,
            }
        )
        logger.debug(
            "Registered Claude tool %r from ToolRef ref=%r name=%r",
            safe_name,
            tool_ref.ref,
            tool_ref.name,
        )

    return result
```

- [ ] 1.2 Create `tests/unit/test_tool_bridge.py` with Claude adapter tests:

```python
"""Unit tests for engine/tool_bridge.py -- all three framework adapters."""

from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal ToolRef stand-in so tests don't depend on the full engine package.
# ---------------------------------------------------------------------------


class _ToolRef:
    """Minimal ToolRef mimic for bridge tests."""

    def __init__(
        self,
        *,
        ref: str | None = None,
        name: str | None = None,
        type: str | None = None,
        description: str | None = None,
        schema_: dict[str, Any] | None = None,
    ) -> None:
        self.ref = ref
        self.name = name
        self.type = type
        self.description = description
        self.schema_ = schema_


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_bridge():
    """Import (or re-import) the tool_bridge module cleanly."""
    for key in list(sys.modules.keys()):
        if "tool_bridge" in key:
            del sys.modules[key]
    import engine.tool_bridge as bridge  # noqa: PLC0415
    return bridge


# ---------------------------------------------------------------------------
# _ref_to_slug
# ---------------------------------------------------------------------------


class TestRefToSlug:
    def test_simple_name(self):
        bridge = _import_bridge()
        assert bridge._ref_to_slug("search") == "SEARCH"

    def test_slash_and_hyphen(self):
        bridge = _import_bridge()
        assert bridge._ref_to_slug("tools/zendesk-mcp") == "TOOLS_ZENDESK_MCP"

    def test_all_special_chars(self):
        bridge = _import_bridge()
        assert bridge._ref_to_slug("my.tool:v2") == "MY_TOOL_V2"


# ---------------------------------------------------------------------------
# to_claude_tools
# ---------------------------------------------------------------------------


class TestToClaudeTools:
    def test_empty_list(self):
        bridge = _import_bridge()
        assert bridge.to_claude_tools([]) == []

    def test_ref_only_tool(self):
        bridge = _import_bridge()
        tool = _ToolRef(ref="tools/zendesk-mcp", description="Zendesk integration")
        result = bridge.to_claude_tools([tool])

        assert len(result) == 1
        tp = result[0]
        assert tp["name"] == "zendesk-mcp"
        assert tp["description"] == "Zendesk integration"
        assert tp["input_schema"]["type"] == "object"
        assert tp["input_schema"]["properties"] == {}

    def test_inline_tool_with_schema(self):
        bridge = _import_bridge()
        schema = {
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        tool = _ToolRef(name="search", description="Search KB", schema_=schema)
        result = bridge.to_claude_tools([tool])

        assert len(result) == 1
        tp = result[0]
        assert tp["name"] == "search"
        assert tp["input_schema"]["properties"] == {"query": {"type": "string"}}
        assert tp["input_schema"]["required"] == ["query"]

    def test_tool_with_no_description_gets_default(self):
        bridge = _import_bridge()
        tool = _ToolRef(ref="tools/order-lookup")
        result = bridge.to_claude_tools([tool])
        assert result[0]["description"] == "Tool: order-lookup"

    def test_tool_name_sanitised(self):
        """Names with chars outside [a-zA-Z0-9_-] are replaced with underscores."""
        bridge = _import_bridge()
        tool = _ToolRef(name="my tool v2!", description="desc")
        result = bridge.to_claude_tools([tool])
        assert result[0]["name"] == "my_tool_v2_"

    def test_tool_name_truncated_to_64_chars(self):
        bridge = _import_bridge()
        tool = _ToolRef(name="a" * 100, description="desc")
        result = bridge.to_claude_tools([tool])
        assert len(result[0]["name"]) == 64

    def test_tool_with_no_name_and_no_ref_is_skipped(self):
        bridge = _import_bridge()
        tool = _ToolRef(description="orphan")
        result = bridge.to_claude_tools([tool])
        assert result == []

    def test_multiple_tools(self):
        bridge = _import_bridge()
        tools = [
            _ToolRef(ref="tools/zendesk-mcp"),
            _ToolRef(name="search"),
            _ToolRef(ref="tools/order-lookup", description="Order lookup"),
        ]
        result = bridge.to_claude_tools(tools)
        assert len(result) == 3
        names = [t["name"] for t in result]
        assert "zendesk-mcp" in names
        assert "search" in names
        assert "order-lookup" in names
```

- [ ] 1.3 Run tests and verify they pass:

```bash
pytest tests/unit/test_tool_bridge.py::TestRefToSlug tests/unit/test_tool_bridge.py::TestToClaudeTools -v
```

- [ ] 1.4 Commit:

```
git add engine/tool_bridge.py tests/unit/test_tool_bridge.py
git commit -m "feat(tool-bridge): add engine/tool_bridge.py with to_claude_tools() adapter"
```

---

## Task 2: Add `to_crewai_tools()` to `engine/tool_bridge.py`

**Why second:** CrewAI's `BaseTool` is a concrete class hierarchy -- the adapter creates dynamic subclasses. No dynamic code generation required (unlike ADK), but does need `httpx` for the `_run()` HTTP call to the registry endpoint.

### Steps

- [ ] 2.1 Append `to_crewai_tools()` to `engine/tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# CrewAI adapter
# ---------------------------------------------------------------------------


def to_crewai_tools(tools: list[Any]) -> list[Any]:
    """Convert a list of ToolRef objects to crewai BaseTool subclass instances.

    Each tool exposes a synchronous _run() that POSTs to the tool's HTTP
    endpoint (resolved from the TOOL_ENDPOINT_* env var) and returns the
    response text.  Tools whose endpoint URL cannot be resolved are skipped
    with a warning.

    Args:
        tools: List of ToolRef instances from AgentConfig.tools.

    Returns:
        List of crewai.tools.BaseTool instances.
    """
    try:
        from crewai.tools import BaseTool as CrewBaseTool  # type: ignore[import-untyped]
        from pydantic import BaseModel as PydanticBaseModel
    except ImportError:
        logger.warning(
            "crewai is not installed -- to_crewai_tools() returns empty list. "
            "Add crewai to your requirements to enable tool injection."
        )
        return []

    result: list[Any] = []

    for tool_ref in tools:
        endpoint = _resolve_endpoint(tool_ref)
        if endpoint is None:
            identifier = tool_ref.ref or tool_ref.name or "<unnamed>"
            logger.warning(
                "No endpoint env var found for tool %r -- skipping. "
                "Set TOOL_ENDPOINT_%s to enable this tool.",
                identifier,
                _ref_to_slug(identifier),
            )
            continue

        raw_name: str | None = tool_ref.name
        if raw_name is None and tool_ref.ref is not None:
            raw_name = tool_ref.ref.split("/")[-1]
        if raw_name is None:
            continue
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name)
        description: str = tool_ref.description or f"Tool: {safe_name}"
        tool_endpoint: str = endpoint

        raw_schema: dict[str, Any] = tool_ref.schema_ or {}
        props: dict[str, Any] = raw_schema.get("properties", {})

        # Dynamically create the pydantic ArgsSchema class.
        if props:
            ArgsSchema = type(  # noqa: N806
                f"{safe_name}Args",
                (PydanticBaseModel,),
                {"__annotations__": {k: str for k in props}},
            )
        else:
            ArgsSchema = type(  # noqa: N806
                f"{safe_name}Args",
                (PydanticBaseModel,),
                {"__annotations__": {"input": str}},
            )

        def _make_run(ep: str, sname: str) -> Any:
            """Factory closes over ep and sname to avoid late-binding."""

            def _run(self: Any, **kwargs: Any) -> str:
                payload = kwargs if kwargs else {"input": getattr(self, "input", "")}
                try:
                    response = httpx.post(ep, json=payload, timeout=30.0)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict):
                        return str(data.get("output", data))
                    return str(data)
                except httpx.HTTPError as exc:
                    logger.error("Tool %r HTTP error: %s", sname, exc)
                    return f"Error calling tool {sname!r}: {exc}"

            return _run

        ToolClass = type(  # noqa: N806
            safe_name,
            (CrewBaseTool,),
            {
                "name": safe_name,
                "description": description,
                "args_schema": ArgsSchema,
                "_run": _make_run(tool_endpoint, safe_name),
            },
        )
        result.append(ToolClass())
        logger.debug("Registered CrewAI tool %r -> endpoint %r", safe_name, tool_endpoint)

    return result
```

- [ ] 2.2 Add `TestToCrewaiTools` class to `tests/unit/test_tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# to_crewai_tools
# ---------------------------------------------------------------------------


class TestToCrewaiTools:
    def _make_mock_crewai(self):
        """Return fake crewai module stubs with a minimal BaseTool."""

        class FakeBaseTool:
            name: str = ""
            description: str = ""
            args_schema: Any = None

            def _run(self, **kwargs: Any) -> str:
                return ""

        fake_crewai_tools = types.ModuleType("crewai.tools")
        fake_crewai_tools.BaseTool = FakeBaseTool  # type: ignore[attr-defined]
        fake_crewai = types.ModuleType("crewai")
        return fake_crewai, fake_crewai_tools

    def test_returns_empty_when_crewai_missing(self):
        with patch.dict(sys.modules, {"crewai": None, "crewai.tools": None}):
            bridge = _import_bridge()
            result = bridge.to_crewai_tools([_ToolRef(ref="tools/search")])
        assert result == []

    def test_skips_tool_with_no_endpoint(self, monkeypatch):
        """Tool without TOOL_ENDPOINT_* env var is skipped, no crash."""
        monkeypatch.delenv("TOOL_ENDPOINT_TOOLS_SEARCH", raising=False)
        fake_crewai, fake_crewai_tools = self._make_mock_crewai()
        with patch.dict(sys.modules, {"crewai": fake_crewai, "crewai.tools": fake_crewai_tools}):
            bridge = _import_bridge()
            result = bridge.to_crewai_tools([_ToolRef(ref="tools/search")])
        assert result == []

    def test_creates_tool_instance_when_endpoint_set(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_TOOLS_ZENDESK_MCP", "http://tool-host/zendesk")
        fake_crewai, fake_crewai_tools = self._make_mock_crewai()
        with patch.dict(sys.modules, {"crewai": fake_crewai, "crewai.tools": fake_crewai_tools}):
            bridge = _import_bridge()
            result = bridge.to_crewai_tools(
                [_ToolRef(ref="tools/zendesk-mcp", description="Zendesk")]
            )
        assert len(result) == 1
        assert result[0].name == "zendesk_mcp"
        assert result[0].description == "Zendesk"

    def test_run_posts_to_endpoint(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        fake_crewai, fake_crewai_tools = self._make_mock_crewai()
        mock_response = MagicMock()
        mock_response.json.return_value = {"output": "found 3 results"}
        mock_response.raise_for_status = MagicMock()

        with patch.dict(sys.modules, {"crewai": fake_crewai, "crewai.tools": fake_crewai_tools}):
            bridge = _import_bridge()
            with patch("httpx.post", return_value=mock_response) as mock_post:
                result = bridge.to_crewai_tools([_ToolRef(name="search", description="Search")])
                assert len(result) == 1
                output = result[0]._run(input="hello world")

        mock_post.assert_called_once_with(
            "http://tool-host/search",
            json={"input": "hello world"},
            timeout=30.0,
        )
        assert output == "found 3 results"

    def test_run_returns_error_string_on_http_failure(self, monkeypatch):
        import httpx as real_httpx
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        fake_crewai, fake_crewai_tools = self._make_mock_crewai()

        with patch.dict(sys.modules, {"crewai": fake_crewai, "crewai.tools": fake_crewai_tools}):
            bridge = _import_bridge()
            with patch("httpx.post", side_effect=real_httpx.ConnectError("refused")):
                result = bridge.to_crewai_tools([_ToolRef(name="search")])
                output = result[0]._run(input="test")

        assert "Error calling tool" in output
        assert "search" in output

    def test_schema_props_become_args_schema_fields(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_LOOKUP", "http://tool-host/lookup")
        fake_crewai, fake_crewai_tools = self._make_mock_crewai()
        schema = {
            "properties": {
                "order_id": {"type": "string"},
                "region": {"type": "string"},
            }
        }
        with patch.dict(sys.modules, {"crewai": fake_crewai, "crewai.tools": fake_crewai_tools}):
            bridge = _import_bridge()
            result = bridge.to_crewai_tools([_ToolRef(name="lookup", schema_=schema)])
        assert len(result) == 1
        fields = result[0].args_schema.__annotations__
        assert "order_id" in fields
        assert "region" in fields
```

- [ ] 2.3 Run tests:

```bash
pytest tests/unit/test_tool_bridge.py::TestToCrewaiTools -v
```

- [ ] 2.4 Commit:

```
git add engine/tool_bridge.py tests/unit/test_tool_bridge.py
git commit -m "feat(tool-bridge): add to_crewai_tools() adapter with dynamic BaseTool subclass"
```

---

## Task 3: Add `to_adk_tools()` to `engine/tool_bridge.py`

**Why third:** ADK uses plain Python callables. Requires building a function with a typed signature derived from the schema -- most complex adapter. Isolated here so failures don't block Tasks 1 and 2.

**Security note on `exec()`:** The code string passed to `exec()` is constructed entirely from internally sanitised values (`safe_name` via `re.sub`, `tool_endpoint` from an env var, `param_parts` derived from schema property names after sanitisation). No user-supplied input ever flows directly into the `exec()` string. The ruff `S102` suppression comment is therefore correct and intentional.

### Steps

- [ ] 3.1 Append `to_adk_tools()` to `engine/tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# Google ADK adapter
# ---------------------------------------------------------------------------


def to_adk_tools(tools: list[Any]) -> list[Callable[..., Any]]:
    """Convert a list of ToolRef objects to Google ADK-compatible callables.

    ADK treats any Python callable with type-annotated parameters and a
    docstring as a tool.  For each ToolRef we dynamically construct an async
    function whose:

    - name is the sanitised tool name (valid Python identifier)
    - docstring is the ToolRef description
    - parameters are derived from the ToolRef schema properties (all typed as
      str; ADK performs its own JSON Schema generation from annotations)
    - body makes an async HTTP POST to the TOOL_ENDPOINT_* endpoint

    The function body is built with exec() so that its __annotations__ reflect
    real parameter names (inspect.signature() must return the correct params
    for ADK's schema introspection to work).  All inputs to exec() are
    internally generated and sanitised -- no user data ever enters the string.

    Tools without a resolvable endpoint are skipped with a warning.

    Args:
        tools: List of ToolRef instances from AgentConfig.tools.

    Returns:
        List of async callables compatible with google.adk.agents.Agent(tools=...).
    """
    result: list[Callable[..., Any]] = []

    for tool_ref in tools:
        endpoint = _resolve_endpoint(tool_ref)
        if endpoint is None:
            identifier = tool_ref.ref or tool_ref.name or "<unnamed>"
            logger.warning(
                "No endpoint env var found for tool %r -- skipping. "
                "Set TOOL_ENDPOINT_%s to enable this tool.",
                identifier,
                _ref_to_slug(identifier),
            )
            continue

        raw_name: str | None = tool_ref.name
        if raw_name is None and tool_ref.ref is not None:
            raw_name = tool_ref.ref.split("/")[-1]
        if raw_name is None:
            continue

        # ADK function names must be valid Python identifiers.
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name).lstrip("_") or "tool"
        description: str = tool_ref.description or f"Tool: {safe_name}"
        tool_endpoint: str = endpoint

        raw_schema: dict[str, Any] = tool_ref.schema_ or {}
        props: dict[str, Any] = raw_schema.get("properties", {})
        required: list[str] = raw_schema.get("required", [])

        # Build parameter list -- required params have no default, optional
        # params default to "".  All are typed as str.
        param_parts: list[str] = []
        for prop_name in props:
            safe_prop = re.sub(r"[^a-zA-Z0-9_]", "_", prop_name)
            if prop_name in required:
                param_parts.append(f"{safe_prop}: str")
            else:
                param_parts.append(f'{safe_prop}: str = ""')

        if not param_parts:
            param_parts = ['input: str = ""']

        # Extract just the parameter name (before the colon) for the payload dict.
        param_names = [p.split(":")[0].strip() for p in param_parts]
        params_str = ", ".join(param_parts)
        payload_str = "{" + ", ".join(f"{repr(n)}: {n}" for n in param_names) + "}"

        func_code = (
            f"async def {safe_name}({params_str}) -> str:\n"
            f"    import httpx as _httpx\n"
            f"    payload = {payload_str}\n"
            f"    async with _httpx.AsyncClient(timeout=30.0) as client:\n"
            f"        try:\n"
            f"            resp = await client.post({tool_endpoint!r}, json=payload)\n"
            f"            resp.raise_for_status()\n"
            f"            data = resp.json()\n"
            f"            if isinstance(data, dict):\n"
            f"                return str(data.get('output', data))\n"
            f"            return str(data)\n"
            f"        except _httpx.HTTPError as exc:\n"
            f"            return f'Error calling tool {safe_name!r}: {{exc}}'\n"
        )

        namespace: dict[str, Any] = {}
        exec(func_code, namespace)  # noqa: S102
        func: Callable[..., Any] = namespace[safe_name]
        func.__doc__ = description

        result.append(func)
        logger.debug(
            "Registered ADK tool %r -> endpoint %r (params: %s)",
            safe_name,
            tool_endpoint,
            params_str,
        )

    return result
```

- [ ] 3.2 Add `TestToAdkTools` class to `tests/unit/test_tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# to_adk_tools
# ---------------------------------------------------------------------------


class TestToAdkTools:
    def test_empty_list(self):
        bridge = _import_bridge()
        assert bridge.to_adk_tools([]) == []

    def test_skips_tool_with_no_endpoint(self, monkeypatch):
        monkeypatch.delenv("TOOL_ENDPOINT_TOOLS_SEARCH", raising=False)
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(ref="tools/search")])
        assert result == []

    def test_returns_callable_when_endpoint_set(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_TOOLS_ZENDESK_MCP", "http://tool-host/zendesk")
        bridge = _import_bridge()
        result = bridge.to_adk_tools(
            [_ToolRef(ref="tools/zendesk-mcp", description="Zendesk")]
        )
        assert len(result) == 1
        assert callable(result[0])

    def test_function_name_is_safe_identifier(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_ORDER_LOOKUP", "http://tool-host/order")
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(ref="tools/order-lookup")])
        assert result[0].__name__ == "order_lookup"

    def test_function_docstring_is_description(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(name="search", description="Search the KB")])
        assert result[0].__doc__ == "Search the KB"

    def test_function_default_doc_when_no_description(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(name="search")])
        assert "search" in result[0].__doc__.lower()

    def test_schema_props_become_params(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_LOOKUP", "http://tool-host/lookup")
        bridge = _import_bridge()
        schema = {
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        }
        result = bridge.to_adk_tools([_ToolRef(name="lookup", schema_=schema)])
        import inspect
        sig = inspect.signature(result[0])
        assert "order_id" in sig.parameters

    def test_no_schema_gets_single_input_param(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(name="search")])
        import inspect
        sig = inspect.signature(result[0])
        assert "input" in sig.parameters

    @pytest.mark.asyncio
    async def test_callable_posts_to_endpoint(self, monkeypatch):
        monkeypatch.setenv("TOOL_ENDPOINT_SEARCH", "http://tool-host/search")
        bridge = _import_bridge()
        result = bridge.to_adk_tools([_ToolRef(name="search")])
        fn = result[0]

        mock_response = MagicMock()
        mock_response.json.return_value = {"output": "3 results"}
        mock_response.raise_for_status = MagicMock()
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            output = await fn(input="hello")

        mock_async_client.post.assert_called_once_with(
            "http://tool-host/search", json={"input": "hello"}
        )
        assert output == "3 results"
```

- [ ] 3.3 Run tests:

```bash
pytest tests/unit/test_tool_bridge.py::TestToAdkTools -v
```

- [ ] 3.4 Run all tool bridge tests to confirm no regressions:

```bash
pytest tests/unit/test_tool_bridge.py -v
```

- [ ] 3.5 Commit:

```
git add engine/tool_bridge.py tests/unit/test_tool_bridge.py
git commit -m "feat(tool-bridge): add to_adk_tools() adapter with dynamically-constructed typed callables"
```

---

## Task 4: Wire `to_claude_tools()` into `claude_sdk_server.py`

**Why fourth:** Claude adapter is pure dict conversion -- simplest wiring. Establishes the `AGENT_TOOLS_JSON` env-var handoff pattern that the other templates copy.

**Wiring strategy:** The runtime (`engine/runtimes/claude_sdk.py`) serialises `AgentConfig.tools` to a JSON string and sets `AGENT_TOOLS_JSON` in the container environment at build time. The server template deserialises it at startup and calls `to_claude_tools()`. This keeps the bridge independent of the full engine package inside the deployed container.

### Steps

- [ ] 4.1 Open `engine/runtimes/templates/claude_sdk_server.py`. Add the following imports after the existing `import anthropic` line (around line 9):

```python
import json

from engine.tool_bridge import to_claude_tools
from engine.config_parser import ToolRef
```

- [ ] 4.2 Add a module-level `_tools` list after the existing `_agent = None` line (around line 75):

```python
_tools: list[dict] = []
```

- [ ] 4.3 In the `startup()` function (lines 79-83), after `_agent = _load_agent()`, add tool loading:

```python
    # --- Tool bridge ---
    global _tools  # noqa: PLW0603
    tools_json = os.getenv("AGENT_TOOLS_JSON", "[]")
    try:
        raw_tools = json.loads(tools_json)
        tool_refs = [ToolRef.model_validate(t) for t in raw_tools]
        _tools = to_claude_tools(tool_refs)
        if _tools:
            logger.info("Loaded %d Claude tool(s) from AGENT_TOOLS_JSON", len(_tools))
    except Exception:
        logger.exception(
            "Failed to load tools from AGENT_TOOLS_JSON -- proceeding with no tools"
        )
        _tools = []
```

- [ ] 4.4 In `_run_agent()` (lines 108-153), find the `kwargs` dict built for `messages.create()`. There are two branches: one for `anthropic.AsyncAnthropic` (around line 117) and one for sync `anthropic.Anthropic` (around line 129). In each branch, after the `if system_prompt: kwargs["system"] = system_prompt` line, add:

```python
        if _tools:
            kwargs["tools"] = _tools
```

Apply this addition to both the `AsyncAnthropic` and the sync `Anthropic` branches.

- [ ] 4.5 Add `TestClaudeSdkServerToolWiring` to `tests/unit/test_tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# Integration: claude_sdk_server startup wires tools
# ---------------------------------------------------------------------------


class TestClaudeSdkServerToolWiring:
    """Verify claude_sdk_server reads AGENT_TOOLS_JSON and populates _tools."""

    def _import_server(self, monkeypatch, tools_json: str = "[]"):
        for key in list(sys.modules.keys()):
            if "claude_sdk_server" in key:
                del sys.modules[key]
        monkeypatch.setenv("AGENT_TOOLS_JSON", tools_json)

        fake_anthropic = types.ModuleType("anthropic")
        fake_anthropic.AsyncAnthropic = MagicMock  # type: ignore[attr-defined]
        fake_anthropic.Anthropic = MagicMock  # type: ignore[attr-defined]

        # Stub the bridge and config_parser so the server can import them.
        fake_engine_tb = types.ModuleType("engine.tool_bridge")
        fake_engine_tb.to_claude_tools = lambda refs: [  # type: ignore[attr-defined]
            {
                "name": (r.name or (r.ref or "").split("/")[-1]),
                "description": "",
                "input_schema": {"type": "object", "properties": {}},
            }
            for r in refs
        ]
        fake_engine_cp = types.ModuleType("engine.config_parser")
        fake_engine_cp.ToolRef = _ToolRef  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "anthropic": fake_anthropic,
                "engine.tool_bridge": fake_engine_tb,
                "engine.config_parser": fake_engine_cp,
            },
        ):
            sys.path.insert(0, "engine/runtimes/templates")
            import claude_sdk_server as srv  # noqa: PLC0415
        return srv

    def test_empty_tools_json_leaves_tools_empty(self, monkeypatch):
        srv = self._import_server(monkeypatch, "[]")
        assert srv._tools == []

    def test_valid_tools_json_populates_tools(self, monkeypatch):
        import asyncio
        tools_payload = json.dumps([
            {"ref": "tools/zendesk-mcp", "description": "Zendesk"},
            {"name": "search", "description": "Search"},
        ])
        srv = self._import_server(monkeypatch, tools_payload)
        asyncio.get_event_loop().run_until_complete(srv.startup())
        assert len(srv._tools) == 2

    def test_malformed_tools_json_does_not_crash(self, monkeypatch):
        import asyncio
        srv = self._import_server(monkeypatch, "{not valid json}")
        asyncio.get_event_loop().run_until_complete(srv.startup())
        assert srv._tools == []
```

- [ ] 4.6 Run tests:

```bash
pytest tests/unit/test_tool_bridge.py::TestClaudeSdkServerToolWiring -v
```

- [ ] 4.7 Run the existing Claude SDK runtime tests to verify no regressions:

```bash
pytest tests/unit/test_runtime_claude_sdk.py -v
```

- [ ] 4.8 Commit:

```
git add engine/runtimes/templates/claude_sdk_server.py tests/unit/test_tool_bridge.py
git commit -m "feat(tool-bridge): wire to_claude_tools() into claude_sdk_server startup"
```

---

## Task 5: Wire `to_crewai_tools()` and `to_adk_tools()` into their server templates

**Why last:** Both templates follow the same `AGENT_TOOLS_JSON` pattern established in Task 4. CrewAI passes tools at `_crew` construction time (tools are per-`Agent` in CrewAI, not per-`Crew` -- see step 5.3). ADK passes tools at `Runner` construction.

### Steps

#### CrewAI wiring

- [ ] 5.1 Open `engine/runtimes/templates/crewai_server.py`. Add after the existing imports block:

```python
import json

from engine.tool_bridge import to_crewai_tools
from engine.config_parser import ToolRef
```

- [ ] 5.2 Add module-level storage after `_crew = None`:

```python
_crewai_tools: list = []
```

- [ ] 5.3 In `startup()` (lines 73-77), after `_crew = _load_agent()`, add:

```python
    # --- Tool bridge ---
    global _crewai_tools  # noqa: PLW0603
    tools_json = os.getenv("AGENT_TOOLS_JSON", "[]")
    try:
        raw_tools = json.loads(tools_json)
        tool_refs = [ToolRef.model_validate(t) for t in raw_tools]
        _crewai_tools = to_crewai_tools(tool_refs)
        if _crewai_tools:
            logger.info("Loaded %d CrewAI tool(s)", len(_crewai_tools))
            # Inject tools into each Agent inside the Crew.
            # CrewAI's Crew has a .agents list; each Agent has a .tools list.
            if hasattr(_crew, "agents"):
                for agent in _crew.agents:
                    if hasattr(agent, "tools") and isinstance(agent.tools, list):
                        agent.tools = list(agent.tools) + _crewai_tools
                        logger.debug(
                            "Injected %d tool(s) into CrewAI agent %r",
                            len(_crewai_tools),
                            getattr(agent, "role", "<unknown>"),
                        )
    except Exception:
        logger.exception("Failed to load CrewAI tools -- proceeding with no tools")
        _crewai_tools = []
```

#### Google ADK wiring

- [ ] 5.4 Open `engine/runtimes/templates/google_adk_server.py`. Add after the existing imports block:

```python
import json

from engine.tool_bridge import to_adk_tools
from engine.config_parser import ToolRef
```

- [ ] 5.5 Add module-level storage after `_runner = None`:

```python
_adk_tools: list = []
```

- [ ] 5.6 In `startup()` (lines 75-89), between `_agent = _load_agent()` and the `Runner(...)` construction, insert:

```python
    # --- Tool bridge ---
    global _adk_tools  # noqa: PLW0603
    tools_json = os.getenv("AGENT_TOOLS_JSON", "[]")
    try:
        raw_tools = json.loads(tools_json)
        tool_refs = [ToolRef.model_validate(t) for t in raw_tools]
        _adk_tools = to_adk_tools(tool_refs)
        if _adk_tools:
            logger.info("Loaded %d ADK tool(s)", len(_adk_tools))
            # ADK LlmAgent exposes .tools as a mutable list; extend it before
            # Runner is constructed so the Runner sees the full tool set.
            if hasattr(_agent, "tools") and isinstance(_agent.tools, list):
                _agent.tools = list(_agent.tools) + _adk_tools
            elif hasattr(_agent, "tools"):
                try:
                    _agent.tools = list(_agent.tools) + _adk_tools
                except Exception:
                    logger.warning(
                        "Could not inject tools into ADK agent -- agent.tools is not mutable"
                    )
    except Exception:
        logger.exception("Failed to load ADK tools -- proceeding with no tools")
        _adk_tools = []
```

#### Tests

- [ ] 5.7 Add `TestCrewAiServerToolWiring` and `TestAdkServerToolWiring` to `tests/unit/test_tool_bridge.py`:

```python
# ---------------------------------------------------------------------------
# Integration: crewai_server startup wires tools
# ---------------------------------------------------------------------------


class TestCrewAiServerToolWiring:
    def _import_server(self, monkeypatch, tools_json: str = "[]"):
        for key in list(sys.modules.keys()):
            if "crewai_server" in key:
                del sys.modules[key]
        monkeypatch.setenv("AGENT_TOOLS_JSON", tools_json)

        class FakeBaseTool:
            name: str = "fake"
            description: str = ""
            args_schema: Any = None

            def _run(self, **kwargs: Any) -> str:
                return ""

        fake_crewai_tools_mod = types.ModuleType("crewai.tools")
        fake_crewai_tools_mod.BaseTool = FakeBaseTool  # type: ignore[attr-defined]
        fake_crewai_mod = types.ModuleType("crewai")

        fake_engine_tb = types.ModuleType("engine.tool_bridge")
        fake_engine_tb.to_crewai_tools = lambda refs: [FakeBaseTool() for _ in refs]  # type: ignore[attr-defined]
        fake_engine_cp = types.ModuleType("engine.config_parser")
        fake_engine_cp.ToolRef = _ToolRef  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "crewai": fake_crewai_mod,
                "crewai.tools": fake_crewai_tools_mod,
                "engine.tool_bridge": fake_engine_tb,
                "engine.config_parser": fake_engine_cp,
            },
        ):
            sys.path.insert(0, "engine/runtimes/templates")
            import crewai_server as srv  # noqa: PLC0415
        return srv

    def test_tools_injected_into_crew_agents(self, monkeypatch):
        import asyncio
        tools_payload = json.dumps([{"name": "search", "description": "Search"}])
        srv = self._import_server(monkeypatch, tools_payload)

        class FakeAgent:
            role = "researcher"
            tools: list = []

        class FakeCrew:
            agents = [FakeAgent()]

        srv._crew = FakeCrew()
        asyncio.get_event_loop().run_until_complete(srv.startup())

        assert len(srv._crewai_tools) == 1
        assert len(FakeCrew.agents[0].tools) == 1

    def test_empty_tools_json_no_injection(self, monkeypatch):
        import asyncio
        srv = self._import_server(monkeypatch, "[]")

        class FakeAgent:
            role = "researcher"
            tools: list = []

        class FakeCrew:
            agents = [FakeAgent()]

        srv._crew = FakeCrew()
        asyncio.get_event_loop().run_until_complete(srv.startup())
        assert srv._crewai_tools == []
        assert FakeCrew.agents[0].tools == []


# ---------------------------------------------------------------------------
# Integration: google_adk_server startup wires tools
# ---------------------------------------------------------------------------


class TestAdkServerToolWiring:
    def _import_server(self, monkeypatch, tools_json: str = "[]"):
        for key in list(sys.modules.keys()):
            if "google_adk_server" in key:
                del sys.modules[key]
        monkeypatch.setenv("AGENT_TOOLS_JSON", tools_json)

        fake_google = types.ModuleType("google")
        fake_adk = types.ModuleType("google.adk")
        fake_runners = types.ModuleType("google.adk.runners")
        fake_sessions = types.ModuleType("google.adk.sessions")

        class FakeRunner:
            def __init__(self, **kwargs: Any):
                pass

        class FakeSessionService:
            pass

        fake_runners.Runner = FakeRunner  # type: ignore[attr-defined]
        fake_sessions.InMemorySessionService = FakeSessionService  # type: ignore[attr-defined]

        fake_engine_tb = types.ModuleType("engine.tool_bridge")
        fake_engine_tb.to_adk_tools = lambda refs: [lambda input="": "result" for _ in refs]  # type: ignore[attr-defined]
        fake_engine_cp = types.ModuleType("engine.config_parser")
        fake_engine_cp.ToolRef = _ToolRef  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "google": fake_google,
                "google.adk": fake_adk,
                "google.adk.runners": fake_runners,
                "google.adk.sessions": fake_sessions,
                "google.genai": types.ModuleType("google.genai"),
                "google.genai.types": types.ModuleType("google.genai.types"),
                "engine.tool_bridge": fake_engine_tb,
                "engine.config_parser": fake_engine_cp,
            },
        ):
            sys.path.insert(0, "engine/runtimes/templates")
            import google_adk_server as srv  # noqa: PLC0415
        return srv

    def test_tools_injected_into_adk_agent(self, monkeypatch):
        import asyncio
        tools_payload = json.dumps([{"name": "search", "description": "Search"}])
        srv = self._import_server(monkeypatch, tools_payload)

        class FakeADKAgent:
            tools: list = []

        srv._agent = FakeADKAgent()
        asyncio.get_event_loop().run_until_complete(srv.startup())

        assert len(srv._adk_tools) == 1
        assert len(FakeADKAgent.tools) == 1

    def test_empty_tools_no_mutation(self, monkeypatch):
        import asyncio
        srv = self._import_server(monkeypatch, "[]")

        class FakeADKAgent:
            tools: list = []

        srv._agent = FakeADKAgent()
        asyncio.get_event_loop().run_until_complete(srv.startup())
        assert srv._adk_tools == []
        assert FakeADKAgent.tools == []
```

- [ ] 5.8 Run new wiring tests:

```bash
pytest tests/unit/test_tool_bridge.py::TestCrewAiServerToolWiring tests/unit/test_tool_bridge.py::TestAdkServerToolWiring -v
```

- [ ] 5.9 Run the complete test file:

```bash
pytest tests/unit/test_tool_bridge.py -v
```

- [ ] 5.10 Run related existing runtime tests to confirm no regressions:

```bash
pytest tests/unit/test_runtime_crewai.py tests/unit/test_runtime_google_adk.py -v
```

- [ ] 5.11 Commit:

```
git add engine/runtimes/templates/crewai_server.py engine/runtimes/templates/google_adk_server.py tests/unit/test_tool_bridge.py
git commit -m "feat(tool-bridge): wire to_crewai_tools() and to_adk_tools() into server templates"
```

---

## Acceptance Criteria

All of the following must be true before this plan is considered complete:

- [ ] `engine/tool_bridge.py` exists with `_ref_to_slug()`, `_resolve_endpoint()`, `to_claude_tools()`, `to_crewai_tools()`, and `to_adk_tools()` all exported
- [ ] `tests/unit/test_tool_bridge.py` exists with >= 30 test functions covering all three adapters and the three server wiring integrations
- [ ] `pytest tests/unit/test_tool_bridge.py -v` exits 0 with no skips
- [ ] `pytest tests/unit/test_runtime_claude_sdk.py tests/unit/test_runtime_crewai.py tests/unit/test_runtime_google_adk.py -v` all pass (no regressions)
- [ ] `claude_sdk_server.py` reads `AGENT_TOOLS_JSON`, calls `to_claude_tools()`, and passes the result as `tools=` in `messages.create()`
- [ ] `crewai_server.py` reads `AGENT_TOOLS_JSON`, calls `to_crewai_tools()`, and injects tools into `_crew.agents[*].tools`
- [ ] `google_adk_server.py` reads `AGENT_TOOLS_JSON`, calls `to_adk_tools()`, and extends `_agent.tools` before `Runner` construction
- [ ] Tools with no matching `TOOL_ENDPOINT_*` env var produce a `logger.warning` and are silently skipped -- no exception propagates to the request handler
- [ ] All new code passes `ruff check engine/tool_bridge.py engine/runtimes/templates/crewai_server.py engine/runtimes/templates/google_adk_server.py engine/runtimes/templates/claude_sdk_server.py`

---

## Implementation Notes

**`AGENT_TOOLS_JSON` env var format:** The value is a JSON array of serialised `ToolRef` objects. Each element is the dict form of a `ToolRef` -- i.e., whatever `ToolRef.model_dump(by_alias=True)` produces. The `engine/runtimes/crewai.py`, `google_adk.py`, and `claude_sdk.py` runtime builder files are responsible for serialising `AgentConfig.tools` and injecting `AGENT_TOOLS_JSON` into the container environment (this is Phase 3 runtime-builder work, separate from this plan -- the server templates read it defensively with a default of `"[]"`).

**`ToolRef.schema_` vs `schema`:** The Pydantic field uses `schema_` as the Python attribute name with `alias="schema"` to avoid shadowing the built-in. The JSON representation uses `"schema"` (the alias). `ToolRef.model_validate(t)` handles the alias transparently, so the server templates pass raw dicts from `json.loads()` directly.

**`exec()` in `to_adk_tools()`:** The `exec()` call builds an async function whose parameter names match the tool's JSON Schema properties exactly (required for ADK's `inspect.signature()` introspection). All inputs are internally generated and sanitised via `re.sub()` before entering the code string -- no user-supplied data flows into `exec()`. The `# noqa: S102` suppression is therefore correct. The `write` hook warning about command injection does not apply here because the code string is never constructed from HTTP request data or other external sources.

**httpx import inside exec'd function:** The dynamically generated function imports `httpx` as `_httpx` inline rather than relying on the outer module's namespace. This is intentional: the `exec()` namespace is isolated, and the inline import ensures the dependency resolves regardless of how the function is later called.

**CrewAI tool injection point:** CrewAI tools are per-`Agent`, not per-`Crew`. The bridge iterates `_crew.agents` and appends to each agent's `.tools` list. If a user's `crew.py` pre-populates agent tools, the bridge tools are appended (non-destructive). If the loaded object has no `.agents` attribute (custom Crew subclass), the injection is silently skipped.
