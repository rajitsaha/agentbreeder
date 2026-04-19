"""Unit tests for the Datadog observability connector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connectors.datadog import DatadogConnector


@pytest.mark.asyncio
async def test_is_available_true():
    connector = DatadogConnector(api_key="test-key")
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
    connector = DatadogConnector(api_key="bad-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await connector.is_available() is False


@pytest.mark.asyncio
async def test_is_available_http_error():
    import httpx

    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                get=AsyncMock(side_effect=httpx.HTTPError("connection refused"))
            )
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        assert await connector.is_available() is False


@pytest.mark.asyncio
async def test_push_metrics_calls_api():
    connector = DatadogConnector(api_key="test-key")
    events = [{"metric": "latency", "value": 100, "agent": "my-agent"}]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_metrics(events)
        mock_http.post.assert_called_once()


@pytest.mark.asyncio
async def test_push_metrics_empty_list_skips_api():
    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        await connector.push_metrics([])
        mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_push_metrics_formats_series_correctly():
    connector = DatadogConnector(api_key="test-key")
    events = [{"metric": "latency", "value": 250, "agent": "search-agent", "env": "staging"}]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_http = MagicMock(post=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_metrics(events)

        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert "series" in payload
        series = payload["series"]
        assert len(series) == 1
        assert series[0]["metric"] == "agentbreeder.agent.latency"
        assert series[0]["points"][0]["value"] == 250.0
        assert "agent:search-agent" in series[0]["tags"]
        assert "env:staging" in series[0]["tags"]


@pytest.mark.asyncio
async def test_scan_returns_monitors():
    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"name": "Agent Error Rate", "message": "Alert on errors"}]
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert len(results) == 1
        assert results[0]["name"] == "Agent Error Rate"
        assert results[0]["source"] == "datadog"
        assert results[0]["type"] == "monitor"


@pytest.mark.asyncio
async def test_scan_returns_empty_on_api_error():
    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert results == []


@pytest.mark.asyncio
async def test_scan_returns_empty_on_http_error():
    import httpx

    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(side_effect=httpx.HTTPError("timeout")))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert results == []


@pytest.mark.asyncio
async def test_scan_maps_message_to_description():
    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "Latency Monitor", "message": "P99 exceeded 5s"},
            {"name": "Cost Monitor"},  # no message key
        ]
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        results = await connector.scan()
        assert results[0]["description"] == "P99 exceeded 5s"
        assert results[1]["description"] == ""


@pytest.mark.asyncio
async def test_push_traces_calls_api():
    connector = DatadogConnector(api_key="test-key")
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
        mock_http = MagicMock(put=AsyncMock(return_value=mock_resp))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await connector.push_traces(traces)
        mock_http.put.assert_called_once()


@pytest.mark.asyncio
async def test_push_traces_empty_list_skips_api():
    connector = DatadogConnector(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client:
        await connector.push_traces([])
        mock_client.assert_not_called()


def test_name_property():
    connector = DatadogConnector(api_key="key")
    assert connector.name == "datadog"


def test_custom_site():
    connector = DatadogConnector(api_key="key", site="datadoghq.eu")
    assert connector._base_url == "https://api.datadoghq.eu"


def test_app_key_included_in_headers():
    connector = DatadogConnector(api_key="key", app_key="app-key-123")
    headers = connector._headers()
    assert headers["DD-APPLICATION-KEY"] == "app-key-123"


def test_no_app_key_omitted_from_headers():
    connector = DatadogConnector(api_key="key")
    headers = connector._headers()
    assert "DD-APPLICATION-KEY" not in headers
