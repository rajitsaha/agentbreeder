# AgentBreeder — Grafana Connector

Pushes AgentBreeder agent fleet metrics and distributed traces to **Grafana** (Loki + Tempo).

## Features

- Availability check via the Grafana `/api/health` endpoint
- Discover existing Grafana dashboards and import them into the AgentBreeder registry
- Push agent invocation metrics as Loki log streams (queryable with LogQL)
- Push distributed traces to Grafana Tempo in OTLP JSON format
- Pre-built dashboard template (`dashboard.json`) for fleet-level observability

## Installation

```bash
pip install "agentbreeder[grafana]"
```

The `grafana` extra adds no new dependencies — `httpx` is already included in the base `agentbreeder` package.

## Configuration

Set the following environment variables:

```bash
GRAFANA_ENDPOINT=https://your-grafana.example.com  # Required — Grafana base URL
GRAFANA_API_KEY=glsa_xxxxxxxxxxxx                  # Required — Grafana service account token
GRAFANA_ORG_ID=1                                   # Optional — Grafana org ID (default: "1")
```

### Grafana Cloud

For Grafana Cloud, use your stack URL:

```bash
GRAFANA_ENDPOINT=https://your-stack-name.grafana.net
GRAFANA_API_KEY=glsa_xxxxxxxxxxxx   # Service account token from Grafana Cloud
```

## Usage

### Python SDK

```python
import os
from connectors.grafana import GrafanaConnector

connector = GrafanaConnector(
    endpoint=os.environ["GRAFANA_ENDPOINT"],
    api_key=os.environ["GRAFANA_API_KEY"],
    org_id=os.environ.get("GRAFANA_ORG_ID", "1"),
)

# Check connectivity
available = await connector.is_available()
print(f"Grafana reachable: {available}")

# Discover dashboards from Grafana
dashboards = await connector.scan()
for d in dashboards:
    print(d["name"], d["url"])

# Push agent metrics (goes to Loki)
await connector.push_metrics([
    {"metric": "latency", "value": 342, "agent": "customer-support-agent", "env": "production"},
    {"metric": "cost_usd", "value": 0.0023, "agent": "customer-support-agent", "env": "production"},
    {"metric": "invocation", "value": 1, "agent": "customer-support-agent", "env": "production"},
])

# Push traces (goes to Tempo)
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
agentbreeder scan --connector grafana
```

This will discover all Grafana dashboards and register them in the AgentBreeder registry.

## Dashboard

Import the pre-built fleet dashboard into Grafana:

1. In the Grafana UI, navigate to **Dashboards → Import**
2. Upload `connectors/grafana/dashboard.json`
3. Select your Prometheus and Loki data sources when prompted
4. Click **Import**

Or via the API:

```bash
curl -X POST "${GRAFANA_ENDPOINT}/api/dashboards/import" \
  -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"dashboard\": $(cat connectors/grafana/dashboard.json), \"overwrite\": true, \"folderId\": 0}"
```

The dashboard includes:
- Fleet overview KPI tiles (active agents, invocations/sec, avg latency, error rate, daily cost)
- P50/P95/P99 latency time series
- Invocations per second by agent
- Token cost per agent
- Error rate by agent with SLO threshold bands
- Live Loki log stream panel for metric events

## Metrics Reference

Metrics are pushed as Loki log streams with structured labels. Each log line contains:

| Label | Description |
|-------|-------------|
| `source` | Always `agentbreeder` |
| `agent` | Agent name |
| `env` | Deployment environment |
| `metric` | Metric name (e.g. `latency`, `cost_usd`, `invocation`) |

Log line format:
```
metric="latency" value=342 agent="customer-support-agent" env="production"
```

Query examples:
```logql
# All invocations for a specific agent
{source="agentbreeder", agent="customer-support-agent"} | logfmt | metric="invocation"

# Average latency over 5 minutes
avg_over_time({source="agentbreeder"} | logfmt | unwrap value [5m]) by (agent)

# Error events
{source="agentbreeder", env="production"} | logfmt | metric="error"
```

## Traces

Traces are pushed to Tempo in OTLP JSON format. Each span carries:

| Attribute | Description |
|-----------|-------------|
| `agent` | Agent name |
| `framework` | Agent framework (langgraph, crewai, etc.) |
| `env` | Deployment environment |
| `service.name` | Always `agentbreeder` |

Query traces in Grafana Explore using **Tempo** data source with `service.name = "agentbreeder"`.
