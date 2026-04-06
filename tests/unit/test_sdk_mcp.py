"""Tests for sdk/python/agenthub/mcp.py — MCPServe decorator and helpers."""

from unittest.mock import MagicMock, patch

from sdk.python.agenthub.mcp import (
    MCPServe,
    _build_input_schema,
    _python_type_to_json_schema,
    serve,
)


class TestPythonTypeToJsonSchema:
    def test_str(self):
        assert _python_type_to_json_schema(str) == "string"

    def test_int(self):
        assert _python_type_to_json_schema(int) == "integer"

    def test_float(self):
        assert _python_type_to_json_schema(float) == "number"

    def test_bool(self):
        assert _python_type_to_json_schema(bool) == "boolean"

    def test_unknown_type_defaults_to_string(self):
        assert _python_type_to_json_schema(list) == "string"

    def test_none_type_defaults_to_string(self):
        assert _python_type_to_json_schema(type(None)) == "string"


class TestBuildInputSchema:
    def test_no_params(self):
        def fn() -> str:
            return "hi"

        schema = _build_input_schema(fn)
        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert "required" not in schema

    def test_required_param(self):
        def fn(name: str) -> str:
            return name

        schema = _build_input_schema(fn)
        assert "name" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["required"] == ["name"]

    def test_optional_param_not_in_required(self):
        def fn(name: str, excited: bool = False) -> str:
            return name

        schema = _build_input_schema(fn)
        assert "name" in schema["properties"]
        assert "excited" in schema["properties"]
        assert schema["properties"]["excited"]["type"] == "boolean"
        assert "name" in schema["required"]
        assert "excited" not in schema["required"]

    def test_multiple_types(self):
        def fn(x: int, y: float, flag: bool) -> str:
            return str(x)

        schema = _build_input_schema(fn)
        assert schema["properties"]["x"]["type"] == "integer"
        assert schema["properties"]["y"]["type"] == "number"
        assert schema["properties"]["flag"]["type"] == "boolean"
        assert set(schema["required"]) == {"x", "y", "flag"}

    def test_no_type_hint_defaults_to_string(self):
        def fn(value) -> str:  # noqa: ANN001
            return str(value)

        schema = _build_input_schema(fn)
        assert schema["properties"]["value"]["type"] == "string"


class TestMCPServe:
    def test_init_defaults(self):
        s = MCPServe()
        assert s.tool_names == []

    def test_init_custom_name(self):
        s = MCPServe(name="my-server")
        assert s.tool_names == []

    def test_tool_decorator_registers(self):
        with patch("sdk.python.agenthub.mcp.FastMCP") as mock_fastmcp:
            mock_server = MagicMock()
            mock_fastmcp.return_value = mock_server
            mock_server.tool.return_value = lambda f: f

            s = MCPServe()

            @s.tool()
            def greet(name: str) -> str:
                """Say hello."""
                return f"Hello {name}"

            assert "greet" in s.tool_names

    def test_tool_decorator_returns_original_function(self):
        with patch("sdk.python.agenthub.mcp.FastMCP") as mock_fastmcp:
            mock_server = MagicMock()
            mock_fastmcp.return_value = mock_server
            mock_server.tool.return_value = lambda f: f

            s = MCPServe()

            @s.tool()
            def add(x: int, y: int) -> int:
                """Add two numbers."""
                return x + y

            assert add(2, 3) == 5

    def test_multiple_tools_registered(self):
        with patch("sdk.python.agenthub.mcp.FastMCP") as mock_fastmcp:
            mock_server = MagicMock()
            mock_fastmcp.return_value = mock_server
            mock_server.tool.return_value = lambda f: f

            s = MCPServe()

            @s.tool()
            def tool_a(x: str) -> str:
                """Tool A."""
                return x

            @s.tool()
            def tool_b(y: int) -> int:
                """Tool B."""
                return y

            assert s.tool_names == ["tool_a", "tool_b"]

    def test_tool_names_returns_copy(self):
        with patch("sdk.python.agenthub.mcp.FastMCP") as mock_fastmcp:
            mock_server = MagicMock()
            mock_fastmcp.return_value = mock_server
            mock_server.tool.return_value = lambda f: f

            s = MCPServe()
            names = s.tool_names
            names.append("injected")
            assert "injected" not in s.tool_names

    def test_run_calls_server(self):
        with patch("sdk.python.agenthub.mcp.FastMCP") as mock_fastmcp:
            mock_server = MagicMock()
            mock_fastmcp.return_value = mock_server

            s = MCPServe()
            s.run()
            mock_server.run.assert_called_once()


class TestModuleSingleton:
    def test_serve_is_mcpserve_instance(self):
        assert isinstance(serve, MCPServe)

    def test_serve_tool_names_is_list(self):
        assert isinstance(serve.tool_names, list)
