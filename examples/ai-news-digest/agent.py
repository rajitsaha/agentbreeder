"""Google ADK agent for the AI news digest.

Exports `root_agent` — picked up by AgentBreeder's server wrapper at runtime.

WORKAROUND: This file exists because AgentBreeder issue #66 is not yet resolved.
Once #66 lands, delete agent.py and use root_agent.yaml alone (Low Code tier).

Run directly for local development:
    python agent.py --once        # fetch and email now
    python agent.py --schedule    # daemon mode, fires daily at DIGEST_HOUR
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import date

import schedule
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm as LiteLlmModel
from tools.impl import fetch_arxiv, fetch_hackernews, fetch_rss, send_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (mirrors root_agent.yaml instruction)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an AI news curator. When the user asks for the daily digest, follow these steps:

1. Call fetch_hackernews, fetch_arxiv, and fetch_rss to gather stories.
   Use limit = NEWS_COUNT / 3 for each (default: 5 each).

2. Write a digest with exactly three labelled sections:

   ## Hacker News Picks
   ## Research Papers (ArXiv)
   ## Industry News (RSS)

3. For each item write 2-3 sentences: what it is and why it matters for AI practitioners.
   Include the URL at the end of each item.

4. Call send_email with:
   - subject: "AI News Digest — {today's date}"
   - body: the full digest text

Be direct. No preamble. No filler phrases. Prioritise novelty and practical impact.
If a source returned no results, note it briefly and continue.
"""

# ---------------------------------------------------------------------------
# Tool wrappers (same impl, ADK-compatible signatures)
# ---------------------------------------------------------------------------


def _fetch_hackernews(limit: int = 5) -> list[dict]:
    """Fetch top AI stories from Hacker News."""
    return fetch_hackernews(limit=limit)


def _fetch_arxiv(limit: int = 5) -> list[dict]:
    """Fetch latest AI/ML papers from ArXiv cs.AI + cs.LG."""
    return fetch_arxiv(limit=limit)


def _fetch_rss(limit: int = 5) -> list[dict]:
    """Fetch AI industry news from TechCrunch, Wired, VentureBeat RSS."""
    return fetch_rss(limit=limit)


def _send_email(subject: str, body: str) -> dict:
    """Send digest to RECIPIENT_EMAILS via Gmail SMTP."""
    return send_email(subject=subject, body=body)


# ---------------------------------------------------------------------------
# root_agent — exported for AgentBreeder's server wrapper
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="ai_news_digest",
    model=LiteLlmModel(
        model=os.environ.get("AGENT_MODEL", "ollama/gemma3:27b"),
        api_base=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    ),
    description="Daily AI news digest — HN + ArXiv + RSS, emailed via Gmail",
    instruction=_SYSTEM_PROMPT,
    tools=[_fetch_hackernews, _fetch_arxiv, _fetch_rss, _send_email],
)

# ---------------------------------------------------------------------------
# Local runner (--once / --schedule)
# ---------------------------------------------------------------------------


async def _run_digest() -> None:
    """Invoke the agent with the digest prompt."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="ai-news-digest", session_service=session_service)
    session = await session_service.create_session(app_name="ai-news-digest", user_id="scheduler")

    prompt = f"Generate today's AI news digest for {date.today().isoformat()} and email it."
    logger.info("Starting digest run: %s", prompt)

    async for event in runner.run_async(
        user_id="scheduler",
        session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
    ):
        if event.is_final_response():
            logger.info("Digest complete: %s", event.content.parts[0].text[:100])


def _run_once() -> None:
    import asyncio

    asyncio.run(_run_digest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI News Digest Agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Run digest immediately and exit")
    group.add_argument(
        "--schedule", action="store_true", help="Run as daemon, fire daily at DIGEST_HOUR"
    )
    args = parser.parse_args()

    if args.once:
        _run_once()
    else:
        hour = int(os.environ.get("DIGEST_HOUR", "8"))
        schedule.every().day.at(f"{hour:02d}:00").do(_run_once)
        logger.info("Scheduler started — digest will run daily at %02d:00", hour)
        while True:
            schedule.run_pending()
            time.sleep(60)
