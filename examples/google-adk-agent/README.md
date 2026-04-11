# Google ADK Agent Example

A simple assistant agent built with the [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/).

## Prerequisites

- A Google Cloud project with the Gemini API enabled
- [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) configured

## ADC Setup

**Option A — Service account key (local dev):**
```bash
cp .env.example .env
# Edit .env and set GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS
```

**Option B — gcloud user credentials (local dev):**
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
```

**Option C — Workload Identity (GCP production):**
No key file needed. Deploy to Cloud Run or GKE with a service account that has the required roles.

## Deploy with AgentBreeder

```bash
# Validate the config
agentbreeder validate

# Deploy locally
agentbreeder deploy --target local

# Deploy to GCP Cloud Run
agentbreeder deploy --target gcp
```

## Agent Structure

- `agent.py` — defines `root_agent` (a `google.adk.agents.Agent`) with a clock tool
- `agent.yaml` — AgentBreeder config (`framework: google_adk`)
- `requirements.txt` — Python dependencies
