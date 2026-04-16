"""Unit tests for tool implementations in tools/impl.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# fetch_hackernews
# ---------------------------------------------------------------------------

HN_API_RESPONSE = {
    "hits": [
        {"title": "GPT-5 released", "url": "https://example.com/gpt5", "points": 500},
        {"title": "Ask HN: Best LLM?", "url": None, "objectID": "40000001", "points": 200},
        {"title": "LLaMA 4 beats GPT-4", "url": "https://example.com/llama4", "points": 300},
    ]
}


def test_fetch_hackernews_returns_correct_count():
    mock_response = MagicMock()
    mock_response.json.return_value = HN_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        from tools.impl import fetch_hackernews

        result = fetch_hackernews(limit=2)

    assert len(result) == 2


def test_fetch_hackernews_correct_api_url():
    mock_response = MagicMock()
    mock_response.json.return_value = HN_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response) as mock_get:
        from tools.impl import fetch_hackernews

        fetch_hackernews(limit=3)
        call_url = mock_get.call_args[0][0]
        call_params = mock_get.call_args[1].get("params", {})
        assert "hn.algolia.com" in call_url
        assert "AI" in call_params.get("query", "") or "query" in str(call_params)


def test_fetch_hackernews_fallback_url_for_ask_hn():
    """Posts with url=None should use the HN item URL via objectID."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hits": [{"title": "Ask HN: LLMs?", "url": None, "objectID": "40000001", "points": 50}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        from tools.impl import fetch_hackernews

        result = fetch_hackernews(limit=1)

    assert result[0]["url"] == "https://news.ycombinator.com/item?id=40000001"


def test_fetch_hackernews_timeout_returns_empty():
    import httpx

    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        from tools.impl import fetch_hackernews

        result = fetch_hackernews(limit=5)

    assert result == []


# ---------------------------------------------------------------------------
# fetch_arxiv
# ---------------------------------------------------------------------------

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need: Revisited</title>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <summary>We revisit the original transformer paper and propose improvements.</summary>
    <published>2024-01-15T18:00:00Z</published>
    <author><name>Jane Doe</name></author>
  </entry>
  <entry>
    <title>Scaling Laws for Neural Language Models v2</title>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <summary>We extend scaling law research to trillion-parameter models.</summary>
    <published>2024-01-14T12:00:00Z</published>
    <author><name>John Smith</name></author>
  </entry>
</feed>"""


def test_fetch_arxiv_returns_correct_count():
    mock_response = MagicMock()
    mock_response.text = ARXIV_XML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        from tools.impl import fetch_arxiv

        result = fetch_arxiv(limit=1)

    assert len(result) == 1


def test_fetch_arxiv_parses_fields():
    mock_response = MagicMock()
    mock_response.text = ARXIV_XML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        from tools.impl import fetch_arxiv

        result = fetch_arxiv(limit=2)

    first = result[0]
    assert first["title"] == "Attention Is All You Need: Revisited"
    assert "arxiv.org/abs/2401.00001" in first["url"]
    assert "revisit" in first["summary"].lower()
    assert first["source"] == "arxiv"


def test_fetch_arxiv_timeout_returns_empty():
    import httpx

    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        from tools.impl import fetch_arxiv

        result = fetch_arxiv(limit=5)

    assert result == []
