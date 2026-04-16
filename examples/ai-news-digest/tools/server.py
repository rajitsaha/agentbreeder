"""MCP tool server for the AI news digest agent.

Exposes fetch_hackernews, fetch_arxiv, fetch_rss, and send_email as MCP tools
using the stdio transport. AgentBreeder's MCP sidecar manages this process
in production; run directly for local dev:

    python tools/server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tools.impl import fetch_arxiv, fetch_hackernews, fetch_rss, send_email

mcp = FastMCP(
    name="news-digest-tools",
)


@mcp.tool()
def fetch_hackernews_tool(limit: int = 5) -> list[dict]:
    """Fetch top AI stories from Hacker News. Returns list of {title, url, points, source}."""
    return fetch_hackernews(limit=limit)


@mcp.tool()
def fetch_arxiv_tool(limit: int = 5) -> list[dict]:
    """Fetch latest AI/ML papers from ArXiv cs.AI + cs.LG. Returns list of {title, url, summary, source}."""
    return fetch_arxiv(limit=limit)


@mcp.tool()
def fetch_rss_tool(limit: int = 5) -> list[dict]:
    """Fetch AI industry news from TechCrunch, Wired, VentureBeat RSS. Returns list of {title, url, summary, source}."""
    return fetch_rss(limit=limit)


@mcp.tool()
def send_email_tool(subject: str, body: str) -> dict:
    """Send digest email to RECIPIENT_EMAILS. Returns {sent_to: int}."""
    return send_email(subject=subject, body=body)


if __name__ == "__main__":
    mcp.run()
