# AI News Digest Agent — Design Spec

**Date:** 2026-04-16  
**Status:** Approved  
**GitHub Issues:** #57 (SMTP connector), #58 (News/RSS connector), #60 (feedparser dep), #61 (schedule CLI), #63 (Ollama runtime gap — all frameworks)

---

## 1. Overview

A daily AI news digest agent built with **Google ADK + Ollama Gemma3:27b** deployed via **AgentBreeder**. The agent fetches top AI stories from three free, no-API-key sources, has Gemma synthesize a grouped digest, then emails it to a configured recipient list via Gmail SMTP.

The project is a **standalone example** (`pip install agentbreeder google-adk litellm`) — not a clone of the AgentBreeder repo. It demonstrates Full Code tier: `agent.yaml` manifest + `agent.py` exporting `root_agent`, plus a companion MCP tool server.

---

## 2. Architecture

```
ai-news-digest/
├── tools/                        ← MCP tool server
│   ├── mcp.yaml                  ← MCP server manifest (mirrors examples/mcp-server/mcp.yaml)
│   ├── server.py                 ← @mcp.tool() decorated tool functions
│   └── requirements.txt          ← fastmcp, feedparser, httpx
├── agent.yaml                    ← AgentBreeder manifest (Full Code tier)
├── agent.py                      ← root_agent + LiteLlmModel(ollama/gemma3:27b)
├── requirements.txt              ← google-adk, litellm[ollama], agentbreeder-sdk
└── .env.example                  ← all required env vars documented
```

### Runtime flow

```
agentbreeder deploy --target local
        │
        ▼
  root_agent (google.adk.Agent)
  model = LiteLlmModel("ollama/gemma3:27b")  ← via localhost:11434
        │
        ├── [MCP tool] fetch_hackernews(limit)  → HN Algolia API
        ├── [MCP tool] fetch_arxiv(limit)       → ArXiv API (cs.AI + cs.LG)
        ├── [MCP tool] fetch_rss(limit)         → TechCrunch AI + Wired AI + VentureBeat AI
        │
        ▼
  Gemma writes grouped digest (3 sections, ~2-3 sentences per item)
        │
        ▼
  [MCP tool] send_email(subject, body, recipients)
        │
        ▼
  Gmail SMTP TLS port 587
```

---

## 3. Components

### 3.1 MCP Tool Server (`tools/`)

Follows `examples/mcp-server/` pattern exactly. Uses `fastmcp` with `@mcp.tool()` decorators.

#### `tools/mcp.yaml`

```yaml
name: news-digest-tools
version: 1.0.0
description: "News fetching and email delivery tools for the AI news digest agent"
transport: stdio
command: python tools/server.py
tools:
  - fetch_hackernews
  - fetch_arxiv
  - fetch_rss
  - send_email
```

#### `tools/server.py` — four tools

| Tool | Source | Implementation |
|------|--------|----------------|
| `fetch_hackernews(limit: int)` | HN Algolia API `hn.algolia.com/api/v1/search` | `httpx.get`, filter `tags=story`, query `"AI OR LLM OR machine learning"`, return title+url+points |
| `fetch_arxiv(limit: int)` | ArXiv API `export.arxiv.org/api/query` | `httpx.get`, `cat=cs.AI+cs.LG`, sort `submittedDate`, parse Atom XML with stdlib `xml.etree` |
| `fetch_rss(limit: int)` | TechCrunch AI + Wired AI + VentureBeat AI RSS | `feedparser.parse()` for each feed, merge entries, dedupe by URL, return top N |
| `send_email(subject, body)` | Gmail SMTP port 587 | `smtplib.SMTP` + `email.mime.text.MIMEText`, reads `SMTP_USER`, `SMTP_PASSWORD`, `RECIPIENT_EMAILS` from env |

**No external API keys required** for the three news tools. Email credentials come from env vars via `secret://` refs in `agent.yaml`.

**Per-source limit:** `NEWS_COUNT // 3` (default `NEWS_COUNT=15` → 5 per source). Configurable via env var.

#### `tools/requirements.txt`

```
fastmcp>=1.0.0
feedparser>=6.0.0
httpx>=0.27.0
```

---

### 3.2 Agent (`agent.yaml` + `agent.py`)

#### `agent.yaml`

```yaml
name: ai-news-digest
version: 1.0.0
description: "Daily AI news digest — fetches HN + ArXiv + RSS, summarises with Gemma3, emails recipients"
team: examples
owner: dev@company.com
tags: [news, digest, ollama, gemma, google-adk, email]

framework: google_adk

model:
  primary: ollama/gemma3:27b
  temperature: 0.4
  max_tokens: 4096

tools:
  - ref: tools/news-digest-tools   # MCP server defined in tools/mcp.yaml

prompts:
  system: |
    You are an AI news curator. When asked for the daily digest:
    1. Call fetch_hackernews, fetch_arxiv, and fetch_rss to gather stories.
    2. Write a digest grouped into three sections:
       ## Hacker News Picks
       ## Research Papers (ArXiv)
       ## Industry News
    3. For each item write 2-3 sentences: what it is, why it matters.
    4. Call send_email with the digest as the body.
    Be direct. No filler. Prioritise novelty and practical impact.

deploy:
  cloud: local
  env_vars:
    LOG_LEVEL: info
    NEWS_COUNT: "15"
    DIGEST_HOUR: "8"
    SMTP_HOST: smtp.gmail.com
    SMTP_PORT: "587"
    OLLAMA_BASE_URL: http://localhost:11434
  secrets:
    - SMTP_USER
    - SMTP_PASSWORD
    - RECIPIENT_EMAILS

google_adk:
  session_backend: memory
  memory_service: memory
  artifact_service: memory
```

#### `agent.py`

Exports `root_agent` — the variable AgentBreeder's server wrapper looks for:

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlmModel
import os

SYSTEM_PROMPT = """
You are an AI news curator. When asked for the daily digest:
1. Call fetch_hackernews, fetch_arxiv, and fetch_rss to gather stories.
2. Write a digest grouped into three sections:
   ## Hacker News Picks
   ## Research Papers (ArXiv)
   ## Industry News
3. For each item write 2-3 sentences: what it is, why it matters.
4. Call send_email with the digest as the body.
Be direct. No filler. Prioritise novelty and practical impact.
"""

root_agent = Agent(
    name="ai-news-digest",
    model=LiteLlmModel(
        model=os.getenv("AGENT_MODEL", "ollama/gemma3:27b"),
        api_base=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ),
    description="Daily AI news digest agent",
    instruction=SYSTEM_PROMPT,
)
```

---

## 4. Data Flow

```
1. Trigger (--once or --schedule at DIGEST_HOUR)
       │
2. root_agent receives: "Generate today's AI news digest and email it."
       │
3. Agent calls fetch_hackernews(limit=5)  ──→ HN Algolia API (HTTPS GET, no auth)
   Agent calls fetch_arxiv(limit=5)       ──→ ArXiv Atom feed (HTTPS GET, no auth)
   Agent calls fetch_rss(limit=5)         ──→ 3 RSS feeds via feedparser (HTTPS GET)
       │
4. Tools return: list of {title, url, summary} dicts as JSON strings
       │
5. Gemma3:27b synthesises digest text (~800-1200 words)
       │
6. Agent calls send_email(
       subject="AI News Digest — {date}",
       body=<digest text>
   )
   # send_email reads RECIPIENT_EMAILS from env internally
       │
7. smtplib sends via Gmail SMTP TLS port 587
       │
8. Agent returns: "Digest sent to N recipients."
```

**Context budget:** 5 HN + 5 ArXiv + 5 RSS = ~15 items × ~100 tokens each ≈ 1,500 tokens input. Well within Gemma3:27b's 128K context window.

---

## 5. Error Handling

| Failure | Behaviour |
|---------|-----------|
| Ollama not running | `LiteLlmModel` raises `ConnectionError` — logged, agent exits with non-zero code. User sees: "Is Ollama running? Start with: ollama serve" |
| HN/ArXiv API timeout | Tool returns `{"error": "timeout", "items": []}` — agent skips that section, notes it in digest |
| RSS feed unreachable | `feedparser` returns empty `entries` — tool skips that feed, continues with others |
| Gmail auth failure | `smtplib.SMTPAuthenticationError` — raised, logged with message "Check SMTP_USER and SMTP_PASSWORD (Gmail App Password required)" |
| `RECIPIENT_EMAILS` not set | `send_email` raises `ValueError` before SMTP connection — fast fail |
| `NEWS_COUNT` not divisible by 3 | Use `NEWS_COUNT // 3` per source (floor), acceptable rounding |

Tools never raise exceptions to the agent — they return structured error dicts. The agent's system prompt instructs it to note missing sections rather than failing the whole digest.

---

## 6. Scheduling

Two modes, one entrypoint in `agent.py __main__`:

```
python agent.py --once              # run immediately, exit
python agent.py --schedule          # daemon, fires daily at DIGEST_HOUR (default 8am)
```

`--schedule` uses the `schedule` library (lightweight, stdlib-only alternative to APScheduler). Fires `run_agent()` once daily at `{DIGEST_HOUR}:00` local time.

**Note:** Once `agentbreeder schedule` CLI command is implemented (#61), this internal `--schedule` flag becomes redundant and can be removed.

---

## 7. Configuration Reference

All configuration via environment variables (no code changes needed to reconfigure):

| Env Var | Default | Description |
|---------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `AGENT_MODEL` | `ollama/gemma3:27b` | LiteLLM model string |
| `NEWS_COUNT` | `15` | Total news items (split evenly across 3 sources) |
| `DIGEST_HOUR` | `8` | Hour (0-23 local time) to send daily digest |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | — | Gmail address (secret) |
| `SMTP_PASSWORD` | — | Gmail App Password (secret) |
| `RECIPIENT_EMAILS` | — | Comma-separated email list (secret) |

---

## 8. Testing

| Test | Type | What it checks |
|------|------|----------------|
| `test_fetch_hackernews` | Unit (mock httpx) | Correct API URL, returns N items, handles timeout gracefully |
| `test_fetch_arxiv` | Unit (mock httpx) | Parses Atom XML correctly, respects limit |
| `test_fetch_rss` | Unit (mock feedparser) | Merges 3 feeds, dedupes by URL, respects limit |
| `test_send_email` | Unit (mock smtplib) | Correct SMTP call, raises on missing RECIPIENT_EMAILS |
| `test_agent_yaml_valid` | Integration | `agentbreeder validate` exits 0 |
| `test_full_digest_run` | E2E (Ollama + mock SMTP) | Agent produces a digest with all 3 sections, calls send_email once |

Test file: `tests/test_tools.py` + `tests/test_agent.py`

---

## 9. AgentBreeder Gaps Exposed (GitHub Issues)

| Issue | Title | Priority |
|-------|-------|----------|
| [#63](https://github.com/rajitsaha/agentbreeder/issues/63) | All runtimes break with Ollama/LiteLLM model strings | P0 — blocks this agent from deploying via `agentbreeder deploy` |
| [#58](https://github.com/rajitsaha/agentbreeder/issues/58) | News/RSS connector (`connectors/news/`) | P1 — tools duplicated per-agent until this exists |
| [#57](https://github.com/rajitsaha/agentbreeder/issues/57) | SMTP email connector (`connectors/email/smtp.py`) | P1 — email logic duplicated per-agent until this exists |
| [#61](https://github.com/rajitsaha/agentbreeder/issues/61) | `agentbreeder schedule` CLI command | P2 — workaround: inline `--schedule` flag |
| [#60](https://github.com/rajitsaha/agentbreeder/issues/60) | Add `feedparser` to optional deps | P2 — workaround: `pip install feedparser` in agent's `requirements.txt` |

**P0 workaround:** Until #63 is fixed, `agent.py` constructs `LiteLlmModel` directly (as shown in section 3.2) rather than relying on AgentBreeder's runtime model injection. The `agentbreeder deploy` pipeline still works — only the automatic model routing is bypassed.

---

## 10. Prerequisites

```bash
# 1. Install Ollama and pull the model
brew install ollama          # macOS
ollama pull gemma3:27b       # ~18GB download

# 2. Install packages
pip install agentbreeder google-adk "litellm[ollama]" fastmcp feedparser httpx schedule

# 3. Configure Gmail App Password
# https://myaccount.google.com/apppasswords (requires 2FA enabled)

# 4. Set env vars
cp .env.example .env
# Edit .env: SMTP_USER, SMTP_PASSWORD, RECIPIENT_EMAILS
```
