"""Unit tests for the Grafana observability connector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connectors.grafana import GrafanaConnector
from connectors.grafana.connector import _parse_label_selector, _to_hex


@pytest.mark.asyncio
async def test_is_available_true():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await connector.is_available() is True


@pytest.mark.asyncio
async def test_is_available_false():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="bad-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await connector.is_available() is False


@pytest.mark.asyncio
async def test_is_available_http_error():
    import httpx

    connector = GrafanaConnector(endpoint="http://unreachable:3000", api_key="key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                get=AsyncMock(side_effect=httpx.HTTPError("connection refused"))
            )
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await connector.is_available() is False


@pytest.mark.asyncio
async def test_scan_returns_dashboards():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "AgentBreeder Fleet", "url": "/d/abc123/agentbreeder-fleet"},
            {"title": "Cost Dashboard", "url": "/d/def456/cost"},
        ]
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert len(results) == 2
        assert results[0]["name"] == "AgentBreeder Fleet"
        assert results[0]["source"] == "grafana"
        assert results[0]["type"] == "dashboard"
        assert results[0]["url"] == "/d/abc123/agentbreeder-fleet"


@pytest.mark.asyncio
async def test_scan_returns_empty_on_api_error():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert results == []


@pytest.mark.asyncio
async def test_scan_returns_empty_on_http_error():
    import httpx

    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(side_effect=httpx.HTTPError("timeout")))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert results == []


@pytest.mark.asyncio
async def test_push_metrics_calls_loki_api():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    events = [{"metric": "latency", "value": 100, "agent": "my-agent", "env": "production"}]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_metrics(events)
        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args.args[0]
        assert "/api/v1/push" in call_url


@pytest.mark.asyncio
async def test_push_metrics_formats_loki_streams():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    events = [
        {"metric": "latency", "value": 300, "agent": "search-agent", "env": "production"},
        {"metric": "cost_usd", "value": 0.002, "agent": "search-agent", "env": "production"},
    ]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_metrics(events)
        payload = mock_http.post.call_args.kwargs["json"]
        assert "streams" in payload
        assert len(payload["streams"]) > 0
        # Each stream has a stream label dict and values list
        for stream in payload["streams"]:
            assert "stream" in stream
            assert "values" in stream
            assert stream["stream"]["source"] == "agentbreeder"


@pytest.mark.asyncio
async def test_push_metrics_empty_list_skips_api():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        await connector.push_metrics([])
        mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_push_traces_calls_tempo_api():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    traces = [
        {
            "trace_id": 111,
            "span_id": 222,
            "name": "agent.invoke",
            "agent": "my-agent",
            "start_time": 1714000000.0,
            "duration_ms": 200,
        }
    ]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_traces(traces)
        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args.args[0]
        assert "/api/traces" in call_url


@pytest.mark.asyncio
async def test_push_traces_otlp_format():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    traces = [
        {
            "trace_id": 12345,
            "span_id": 67890,
            "agent": "support-agent",
            "framework": "langgraph",
            "start_time": 1714000000.0,
            "duration_ms": 150,
            "error": False,
        }
    ]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_traces(traces)

        payload = mock_http.post.call_args.kwargs["json"]
        assert "resourceSpans" in payload
        resource_spans = payload["resourceSpans"]
        assert len(resource_spans) == 1
        scope_spans = resource_spans[0]["scopeSpans"]
        spans = scope_spans[0]["spans"]
        assert len(spans) == 1
        span = spans[0]
        assert span["name"] == "agentbreeder.agent.invoke"
        # Verify attributes
        attr_keys = {a["key"] for a in span["attributes"]}
        assert "agent" in attr_keys
        assert "framework" in attr_keys
        assert "service.name" in attr_keys


@pytest.mark.asyncio
async def test_push_traces_empty_list_skips_api():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_test")
    with patch("httpx.AsyncClient") as mock_client:
        await connector.push_traces([])
        mock_client.assert_not_called()


def test_name_property():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="key")
    assert connector.name == "grafana"


def test_trailing_slash_stripped_from_endpoint():
    connector = GrafanaConnector(endpoint="http://grafana:3000/", api_key="key")
    assert connector._endpoint == "http://grafana:3000"


def test_headers_include_auth_and_org():
    connector = GrafanaConnector(endpoint="http://grafana:3000", api_key="glsa_abc", org_id="42")
    headers = connector._headers()
    assert headers["Authorization"] == "Bearer glsa_abc"
    assert headers["X-Scope-OrgID"] == "42"


def test_parse_label_selector():
    result = _parse_label_selector('{source="agentbreeder",agent="foo",env="prod"}')
    assert result == {"source": "agentbreeder", "agent": "foo", "env": "prod"}


def test_to_hex_32_chars():
    result = _to_hex(255)
    assert len(result) == 32
    assert result.endswith("ff")


def test_to_hex_16_chars():
    result = _to_hex(255, width=16)
    assert len(result) == 16
    assert result.endswith("ff")
