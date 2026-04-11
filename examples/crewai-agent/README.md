# CrewAI Example — Research & Writer Crew

A minimal two-agent CrewAI crew deployed with AgentBreeder.

## What it does

1. **Researcher** — gathers facts and key points on any topic you provide.
2. **Writer** — turns those findings into a concise, readable report.

## Run locally

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY

agentbreeder deploy --target local
```

## Call the deployed agent

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"topic": "quantum computing"}}'
```

## Validate before deploying

```bash
agentbreeder validate
```
