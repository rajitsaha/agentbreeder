# Deployment Guide

## Local deployment (Docker)

The fastest way to get an agent running locally:

```bash
# Start the full stack
agentbreeder quickstart

# Or start just the platform
agentbreeder up

# Deploy an agent
agentbreeder deploy ./agent.yaml --target local

# Chat with it
agentbreeder chat my-agent
agentbreeder chat my-agent --local   # use Ollama, no API server needed
```

## AWS ECS Fargate

```bash
# Prerequisites
aws configure                    # set up AWS CLI credentials
# Required IAM permissions: ECS, ECR, CloudFormation, IAM

# Deploy
agentbreeder deploy ./agent.yaml --target aws --region us-east-1

# Check status
agentbreeder status my-agent

# View logs
agentbreeder logs my-agent

# Tear down
agentbreeder teardown my-agent
```

The deployer provisions: ECR registry, ECS cluster, Fargate task definition, ALB, IAM roles, CloudWatch log group.

## GCP Cloud Run

```bash
# Prerequisites
gcloud auth login
gcloud config set project MY_PROJECT
gcloud services enable run.googleapis.com containerregistry.googleapis.com

# Deploy
agentbreeder deploy ./agent.yaml --target gcp --region us-central1

# Check status
agentbreeder status my-agent
```

## Azure Container Apps

```bash
# Prerequisites
az login
az extension add --name containerapp

# Deploy
agentbreeder deploy ./agent.yaml --target azure --region eastus
```

## Kubernetes (EKS / GKE / AKS / self-hosted)

```yaml
# agent.yaml
deploy:
  cloud: kubernetes
  runtime: deployment
  resources:
    cpu: "1"
    memory: "2Gi"
  scaling:
    min: 2
    max: 20
```

```bash
agentbreeder deploy ./agent.yaml --target kubernetes --context my-k8s-context
```

## Claude Managed Agents (Anthropic)

```yaml
deploy:
  cloud: claude-managed
claude_managed:
  environment:
    networking: unrestricted
  tools:
    - type: agent_toolset_20260401
```

No container is built. Anthropic manages the runtime entirely.

## The deploy pipeline

Every deployment runs these steps in order:

1. **Parse & validate** agent.yaml against the JSON Schema
2. **RBAC check** — fail fast if user doesn't have permission
3. **Dependency resolution** — fetch all registry refs (tools, prompts, models)
4. **Container build** — framework-specific Dockerfile generated and built
5. **Infrastructure provision** — cloud resources created via Pulumi
6. **Deploy & health check** — wait for agent to be healthy
7. **Auto-register** — agent registered in org-wide registry
8. **Return endpoint URL**

Every step is atomic. If any step fails, the deploy rolls back completely.
