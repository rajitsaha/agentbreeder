# Claude SDK Agent Example

A minimal AgentBreeder agent built with the Anthropic Claude SDK, demonstrating tool use.

## Quick start

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

agentbreeder validate
agentbreeder deploy --target local
```

## How it works

`agent.py` exports `agent = AsyncAnthropic()`. The AgentBreeder server wrapper
discovers this client and calls `client.messages.create()` on each `/invoke` request,
using `AGENT_MODEL` and `AGENT_SYSTEM_PROMPT` from the environment.

The file also contains `weather_agent`, a fully self-contained async callable that
runs a multi-turn tool-use loop. Swap the `agent` export to `weather_agent` to use it.

## Endpoints

- `GET /health` — liveness check
- `POST /invoke` — `{"input": "What is the weather in Tokyo?"}` → `{"output": "..."}`
