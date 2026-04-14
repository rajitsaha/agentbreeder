# Multi-Platform Deployment Design

**Date:** 2026-04-14
**Status:** Approved — pending implementation plan
**Scope:** Implement all stub deployers + add two new targets (AWS App Runner, Claude Managed Agents)

---

## Background

AgentBreeder's `engine/deployers/` layer already has the right abstractions:
- `BaseDeployer` abstract interface (`provision → deploy → health_check → teardown → get_logs`)
- `CloudType` enum: `aws | azure | gcp | kubernetes | local`
- **Fully implemented:** `GCPCloudRunDeployer`, `DockerComposeDeployer`
- **Stubs (1 line):** `aws_ecs.py`, `kubernetes.py`, `azure_container_apps.py`, `mcp_sidecar.py`

This spec defines the design for completing all stubs, adding two new targets (AWS App Runner, Claude Managed Agents), and the `agent.yaml` changes required.

---

## Deployer Matrix

| Target | `cloud` value | `runtime` value | Status |
|--------|--------------|-----------------|--------|
| Local Docker Compose | `local` | `docker-compose` | ✅ Implemented |
| GCP Cloud Run | `gcp` | `cloud-run` | ✅ Implemented |
| AWS ECS/Fargate | `aws` | `ecs-fargate` | 🔴 Stub → implement |
| AWS App Runner | `aws` | `app-runner` | 🆕 New file |
| Generic Kubernetes | `kubernetes` | `deployment` | 🔴 Stub → implement |
| Azure Container Apps | `azure` | `container-apps` | 🔴 Stub → implement |
| Claude Managed Agents | `claude-managed` | *(n/a)* | 🆕 New file + CloudType value |

---

## Architecture Principles

### Container deployers (AWS ECS, App Runner, Kubernetes, Azure)
All four follow the same pipeline as the existing GCP deployer:
```
Build image → Push to registry → Provision infra → Deploy service → Health check → Register
```
Each deployer:
- Extracts its cloud-specific config from `deploy.env_vars` using a prefixed convention (`AWS_`, `K8S_`, `AZURE_`)
- Filters those prefix keys out of the container's own environment
- Returns a plain HTTPS `endpoint_url`
- Implements all five `BaseDeployer` methods

### Claude Managed Agents deployer
Fundamentally different — **no container build step**:
```
Map agent.yaml → Anthropic API → Create Agent + Environment → Store IDs
```
- `builder.py` skips the build phase when `cloud == claude-managed`
- Returns an `anthropic://agents/{agent_id}?env={environment_id}` reference as `endpoint_url`
- `agentbreeder chat` detects the `anthropic://` scheme and creates a session + streams events

---

## Per-Deployer Design

### 1. AWS ECS/Fargate (`engine/deployers/aws_ecs.py`)

**Infrastructure:**
- Elastic Container Registry (ECR) for images
- ECS Cluster (Fargate launch type, created if absent)
- ECS Task Definition + Service
- Application Load Balancer → target group → service

**Config via `deploy.env_vars` (`AWS_` prefix, filtered from container env):**

```yaml
deploy:
  cloud: aws
  runtime: ecs-fargate
  region: us-east-1
  env_vars:
    AWS_ACCOUNT_ID: "123456789012"
    AWS_VPC_ID: vpc-abc123
    AWS_SUBNET_IDS: subnet-a,subnet-b        # comma-separated
    AWS_SECURITY_GROUP_IDS: sg-xyz
    AWS_ECR_REPO: agentbreeder               # default: "agentbreeder"
    AWS_ECS_CLUSTER: agentbreeder            # default: "agentbreeder"
    AWS_EXECUTION_ROLE_ARN: arn:aws:iam::...  # optional
    AWS_TASK_ROLE_ARN: arn:aws:iam::...       # optional
```

**Deploy flow:**
1. `_ensure_ecr_repo()` — create repo if absent
2. Build + tag + push image to ECR
3. `_register_task_definition()` — CPU/memory from `deploy.resources`; inject `AGENT_NAME`, `AGENT_VERSION`, `AGENT_FRAMEWORK` env vars
4. `_ensure_alb()` — create ALB + target group + listener if absent
5. `_create_or_update_service()` — create or force-new-deployment on existing service
6. Poll service until `runningCount >= 1`
7. Return ALB DNS as `endpoint_url`

**Scaling:** Application Auto Scaling target tracking on ECS service CPU (`deploy.scaling.target_cpu`)

**SDK deps:** `boto3`

---

### 2. AWS App Runner (`engine/deployers/aws_app_runner.py`)

**Infrastructure:**
- ECR repo for images
- App Runner Service (no VPC/ALB/cluster needed)

**Config via `deploy.env_vars`:**

```yaml
deploy:
  cloud: aws
  runtime: app-runner
  region: us-east-1
  env_vars:
    AWS_ACCOUNT_ID: "123456789012"
    AWS_ECR_REPO: agentbreeder
    AWS_APP_RUNNER_ROLE_ARN: arn:aws:iam::...  # ECR access role, optional
```

**Deploy flow:**
1. `_ensure_ecr_repo()` — shared with ECS deployer via helper
2. Build + tag + push image to ECR
3. `_create_or_update_service()` — App Runner CreateService or UpdateService (image URI + port 8080)
4. Map `deploy.scaling` → App Runner `AutoScalingConfiguration` (min/max concurrency)
5. Poll until `Status == RUNNING`
6. Return `ServiceUrl` as `endpoint_url`

**Parallel to GCP Cloud Run** — same "push image, get URL" pattern, minimal config, no infra to manage.

**SDK deps:** `boto3`

---

### 3. Generic Kubernetes (`engine/deployers/kubernetes.py`)

**Infrastructure:**
- Any K8s cluster (local `k3d`/`kind`, EKS, GKE, AKS, bare metal)
- User-provided kubeconfig

**Config via `deploy.env_vars` (`K8S_` prefix, filtered from container env):**

```yaml
deploy:
  cloud: kubernetes
  env_vars:
    K8S_NAMESPACE: default
    K8S_IMAGE_REGISTRY: ghcr.io/myorg       # registry to push image to
    K8S_KUBECONFIG: /path/to/kubeconfig     # or K8S_KUBECONFIG_B64 for base64
    K8S_INGRESS_CLASS: nginx                # optional
    K8S_INGRESS_HOST: agent.mycompany.com   # optional; if absent, use LoadBalancer
    K8S_IMAGE_PULL_SECRET: regcred          # optional
```

**Generated K8s manifests (per agent):**
- `Deployment` — image, resource limits, liveness + readiness probes at `/health`, env vars
- `Service` — `ClusterIP` if ingress host set, `LoadBalancer` otherwise
- `HorizontalPodAutoscaler` — min/max replicas from `deploy.scaling`, CPU target from `deploy.scaling.target_cpu`
- `Ingress` — only if `K8S_INGRESS_HOST` is set; uses `K8S_INGRESS_CLASS`

**Deploy flow:**
1. Build + push image to `K8S_IMAGE_REGISTRY`
2. Render manifests from in-memory templates (no Helm dependency)
3. Apply via `kubernetes` Python client (`apply_namespaced_*`)
4. Watch Deployment rollout until all replicas `Available`
5. Return LoadBalancer external IP or Ingress hostname as `endpoint_url`

**SDK deps:** `kubernetes` (Python client)

---

### 4. Azure Container Apps (`engine/deployers/azure_container_apps.py`)

**Infrastructure:**
- Azure Container Registry (ACR) for images
- Container Apps Environment (shared managed environment)
- Container App (per agent)

**Config via `deploy.env_vars` (`AZURE_` prefix, filtered from container env):**

```yaml
deploy:
  cloud: azure
  runtime: container-apps
  region: eastus
  env_vars:
    AZURE_SUBSCRIPTION_ID: "..."
    AZURE_RESOURCE_GROUP: agentbreeder-rg
    AZURE_ACR_NAME: agentbreeder              # Azure Container Registry name
    AZURE_ENVIRONMENT_NAME: agentbreeder-env   # Container Apps Environment
    AZURE_CLIENT_ID: "..."                     # for managed identity (optional)
```

**Auth:** Azure DefaultAzureCredential (env vars → managed identity → CLI → VS Code)

**Deploy flow:**
1. `_ensure_acr()` — create ACR if absent
2. Build + tag + push image to ACR
3. `_ensure_environment()` — create Container Apps Environment if absent
4. `_create_or_update_container_app()` — create or update Container App
   - Map `deploy.resources` → container resources
   - Map `deploy.scaling` → KEDA scale rules (min/max replicas, HTTP concurrency)
   - Scale-to-zero by default (`minReplicas: 0`)
5. Poll until `provisioningState == Succeeded`
6. Return `https://{app}.{env}.{region}.azurecontainerapps.io` as `endpoint_url`

**SDK deps:** `azure-mgmt-appcontainers`, `azure-mgmt-containerregistry`, `azure-identity`

---

### 5. Claude Managed Agents (`engine/deployers/claude_managed.py`)

**Infrastructure:** Anthropic-hosted (zero infra to provision)

**New `CloudType` value:** `claude-managed`

**New `agent.yaml` config block (alongside `claude_sdk:`, `google_adk:`):**

```yaml
deploy:
  cloud: claude-managed

claude_managed:
  environment:
    networking: unrestricted      # unrestricted | restricted
  tools:
    - type: agent_toolset_20260401   # full built-in toolset (default)
  # mcp_servers inherited from top-level tools[] entries that are MCP refs
```

**Mapping from `agent.yaml` → Anthropic API:**

| `agent.yaml` field | Anthropic API field |
|-------------------|-------------------|
| `model.primary` | `model` |
| `prompts.system` (resolved) | `system` |
| `claude_managed.tools` | `tools` |
| `tools[]` MCP refs | `mcp_servers` |
| `name` | `name` |

**Deploy flow:**
1. Resolve system prompt from registry (same as all other deployers)
2. `POST /v1/agents` with mapped fields → `agent_id`
3. `POST /v1/environments` with `claude_managed.environment` config → `environment_id`
4. Store `anthropic://agents/{agent_id}?env={environment_id}` as `endpoint_url`
5. Register in registry (standard governance step — never skipped)

**No container build.** `engine/builder.py` checks `config.deploy.cloud == "claude-managed"` and skips the build phase entirely.

**Session invocation:** `agentbreeder chat` detects `anthropic://` scheme:
- Creates a session (`POST /v1/sessions`)
- Sends events (`POST /v1/sessions/{id}/events`)
- Streams responses (SSE from `GET /v1/sessions/{id}/stream`)

**SDK deps:** `anthropic` (already a dep for the Claude SDK runtime)

**Beta header required:** `anthropic-beta: managed-agents-2026-04-01`

---

## `agent.yaml` Changes

### `CloudType` enum addition

```python
class CloudType(enum.StrEnum):
    aws = "aws"
    azure = "azure"
    gcp = "gcp"
    kubernetes = "kubernetes"
    local = "local"
    claude_managed = "claude-managed"   # NEW
```

### New `claude_managed` config block (optional, top-level)

```python
class ClaudeManagedEnvironmentConfig(BaseModel):
    networking: Literal["unrestricted", "restricted"] = "unrestricted"

class ClaudeManagedToolConfig(BaseModel):
    type: str  # e.g. "agent_toolset_20260401"

class ClaudeManagedConfig(BaseModel):
    environment: ClaudeManagedEnvironmentConfig = ClaudeManagedEnvironmentConfig()
    tools: list[ClaudeManagedToolConfig] = [
        ClaudeManagedToolConfig(type="agent_toolset_20260401")
    ]
```

### `DeployConfig` runtime field

```python
class RuntimeType(enum.StrEnum):
    ecs_fargate = "ecs-fargate"
    app_runner = "app-runner"
    cloud_run = "cloud-run"
    container_apps = "container-apps"
    deployment = "deployment"          # generic K8s
    docker_compose = "docker-compose"

class DeployConfig(BaseModel):
    cloud: CloudType
    runtime: RuntimeType | None = None  # defaulted per cloud in deployer registry
    ...
```

---

## Deployer Registry

`engine/deployers/__init__.py` routes `(cloud, runtime)` → deployer class:

```python
def get_deployer(config: AgentConfig) -> BaseDeployer:
    cloud = config.deploy.cloud
    runtime = config.deploy.runtime

    match (cloud, runtime):
        case ("local", _):
            return DockerComposeDeployer()
        case ("gcp", _):
            return GCPCloudRunDeployer()
        case ("aws", "app-runner"):
            return AWSAppRunnerDeployer()
        case ("aws", _):                      # default: ecs-fargate
            return AWSECSDeployer()
        case ("kubernetes", _):
            return KubernetesDeployer()
        case ("azure", _):
            return AzureContainerAppsDeployer()
        case ("claude-managed", _):
            return ClaudeManagedDeployer()
        case _:
            raise ValueError(f"Unknown deploy target: cloud={cloud}, runtime={runtime}")
```

---

## Testing Strategy

Every deployer is tested at three levels:

### Unit tests (`tests/unit/deployers/`)
- Config extraction: valid YAML → correct deployer config object
- Manifest generation (K8s): snapshot test on generated manifests
- Error cases: missing required env vars raise `ValueError` with clear message
- Mock all cloud SDK calls

### Integration tests (`tests/integration/deployers/`)
- Full deploy → health check → teardown cycle against real cloud
- Uses `examples/langgraph-agent/` as the test agent
- Gated behind env var flags (`RUN_AWS_INTEGRATION_TESTS=1`, etc.)
- CI runs these on-demand, not on every PR

### E2E test (per deployer)
- Deploy real agent, send real inference request, assert valid JSON response
- Verify registry entry created post-deploy
- Verify teardown removes all cloud resources

### Cloud environment setup (to be done before integration testing)

| Cloud | Setup needed |
|-------|-------------|
| **AWS** | Create IAM user with ECR/ECS/ALB/AppRunner perms; create VPC + subnets; create ECS cluster |
| **Kubernetes** | Spin up local `k3d` cluster OR configure access to existing EKS/GKE/AKS |
| **Azure** | Create subscription + resource group + ACR + Container Apps Environment |
| **Claude Managed** | Verify Anthropic API key has `managed-agents-2026-04-01` beta access |

*Cloud environment setup will be done collaboratively after this issue is created.*

---

## Implementation Phases

### Phase 1 — AWS (ECS/Fargate + App Runner)
- Implement `aws_ecs.py` (full `BaseDeployer`)
- Add `engine/deployers/aws_app_runner.py` (new file)
- Update deployer registry in `__init__.py`
- Unit + integration tests
- Update `agent.yaml` schema with AWS env var docs

### Phase 2 — Kubernetes
- Implement `kubernetes.py` (manifest generation + apply)
- Unit tests (snapshot manifests), integration test against `k3d`
- Update `agent.yaml` schema

### Phase 3 — Azure Container Apps
- Implement `azure_container_apps.py`
- Unit + integration tests
- Update `agent.yaml` schema

### Phase 4 — Claude Managed Agents
- Add `claude-managed` to `CloudType` enum
- Add `ClaudeManagedConfig` to `config_parser.py`
- Implement `engine/deployers/claude_managed.py`
- Wire `engine/builder.py` to skip build for `cloud: claude-managed`
- Update `agentbreeder chat` to handle `anthropic://` endpoints
- Integration test against real Anthropic API

### Phase 5 — Documentation + Examples
- Update `docs/` with per-target quickstart
- Add `examples/` agent configs for each cloud target
- Update `CLAUDE.md` supported stack matrix
