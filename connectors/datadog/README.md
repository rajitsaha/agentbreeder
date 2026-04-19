# AgentBreeder — Datadog Connector

Pushes AgentBreeder agent fleet metrics and distributed traces to **Datadog APM**.

## Features

- Availability check via the Datadog API validate endpoint
- Discover existing Datadog monitors and import them into the AgentBreeder registry
- Push agent invocation metrics as Datadog series points (latency, cost, error rate)
- Push distributed traces to Datadog APM
- Pre-built dashboard template (`dashboard.json`) for fleet-level observability

## Installation

```bash
pip install "agentbreeder[datadog]"
```

The `datadog` extra adds no new dependencies — `httpx` is already included in the base `agentbreeder` package.

## Configuration

Set the following environment variables:

```bash
DD_API_KEY=your-datadog-api-key          # Required
DD_APP_KEY=your-datadog-application-key  # Optional — needed for monitor scanning
DD_SITE=datadoghq.com                    # Optional — default: datadoghq.com
                                         # EU: datadoghq.eu
                                         # US3: us3.datadoghq.com
                                         # US5: us5.datadoghq.com
                                         # Gov: ddog-gov.com
```

## Usage

### Python SDK

```python
import os
from connectors.datadog import DatadogConnector

connector = DatadogConnector(
    api_key=os.environ["DD_API_KEY"],
    app_key=os.environ.get("DD_APP_KEY", ""),
    site=os.environ.get("DD_SITE", "datadoghq.com"),
)

# Check connectivity
available = await connector.is_available()
print(f"Datadog reachable: {available}")

# Discover monitors from Datadog
monitors = await connector.scan()
for m in monitors:
    print(m["name"], m["type"])

# Push agent metrics
await connector.push_metrics([
    {"metric": "latency", "value": 342, "agent": "customer-support-agent", "env": "production"},
    {"metric": "cost_usd", "value": 0.0023, "agent": "customer-support-agent", "env": "production"},
    {"metric": "invocation", "value": 1, "agent": "customer-support-agent", "env": "production"},
])

# Push traces
await connector.push_traces([
    {
        "trace_id": 123456789,
        "span_id": 987654321,
        "name": "agentbreeder.agent.invoke",
        "agent": "customer-support-agent",
        "framework": "langgraph",
        "start_time": 1714000000.0,
        "duration_ms": 342,
        "error": False,
    }
])
```

### agentbreeder scan

```bash
agentbreeder scan --connector datadog
```

This will discover all Datadog monitors and register them in the AgentBreeder registry.

## Dashboard

Import the pre-built fleet dashboard into Datadog:

```bash
curl -X POST "https://api.datadoghq.com/api/v1/dashboard" \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  -H "Content-Type: application/json" \
  -d @connectors/datadog/dashboard.json
```

The dashboard includes:
- Agent invocations per minute
- P50/P95/P99 latency time series
- Error rate with SLO threshold marker
- Token cost per agent
- Summary KPI tiles (total invocations, active agents, avg latency, total cost)
- Top agents by invocation volume and cost
- Latency heatmap by agent

## Metrics Reference

| Metric | Type | Description |
|--------|------|-------------|
| `agentbreeder.agent.invocation` | count | Agent invocation events |
| `agentbreeder.agent.latency` | gauge | End-to-end latency in milliseconds |
| `agentbreeder.agent.cost_usd` | gauge | Token cost in USD per invocation |
| `agentbreeder.agent.error` | count | Failed invocations |
| `agentbreeder.agent.tokens` | gauge | Total tokens consumed |

All metrics carry `agent` and `env` tags automatically.
