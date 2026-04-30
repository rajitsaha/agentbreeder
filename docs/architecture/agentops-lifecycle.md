# AgentOps Lifecycle — Create → Git → Approve → Deploy → Registry

> **Status:** Design (not yet implemented). Tracked under epic `#TBD` (linked once filed).
> **Author:** AgentBreeder team, 2026-04-30.
> **Audience:** Platform engineers extending AgentBreeder; ops engineers wiring it into their org.
> **Updates v2.0/v2.1:** This doc is the connective tissue between the create primitives shipped in v2.0/v2.1 (CLI, IDE/SDK, dashboard builders, registries, deployers) and the governance primitives that already exist as scaffolding (`/api/v1/git`, `/api/v1/approvals`, RBAC ACL migration 015, service principals).

---

## 1. The problem

AgentBreeder shipped strong primitives in v2.0/v2.1 — a CLI, a polyglot SDK, a visual builder with Save/Validate/Deploy, registries for agents/prompts/tools/MCP/RAG/eval, multi-cloud deployers (AWS ECS, GCP Cloud Run, Azure Container Apps, Kubernetes, App Runner), an approval queue, and a git workflow CLI (`submit` / `review` / `publish`).

But these primitives are **not connected**. Today:

1. The dashboard's `Save` writes to the workspace DB. **Nothing goes to GitHub.** A user iterating in the visual builder leaves no commit trail.
2. `agentbreeder submit` (the CLI) creates a PR — but the dashboard has no equivalent button. Code-shy authors (PMs, analysts, citizen builders) can't get their work reviewed.
3. The `/approvals` page shows an internal `approval_queue` table that is **decoupled from GitHub PRs**. Approving in the dashboard does nothing on the PR; merging the PR does nothing in the queue.
4. Deploys hit *one* cloud, picked from `agent.yaml` `deploy.cloud`. There is no notion of *environments* (dev/staging/prod), no promotion gate between them, and no per-env registry.
5. Cloud credentials are pulled from the deployer's environment at deploy time. There is no per-environment service principal binding, no audit of "who deployed v1.2.0 to production AWS."
6. The registry is a single-DB primitive. There is no replication, no environment isolation, no `git_ref` stamp on the row.

The result: **AgentOps stops at "I built an agent." It doesn't continue through "I shipped an agent to production with appropriate review and audit."**

---

## 2. Goals and non-goals

### Goals
- Every artifact a user creates (agent, prompt, tool, MCP server, RAG index, eval) **lives in git** as the source of truth. The dashboard, CLI, and IDE are all editors that produce git commits.
- A single, unified review surface: the same PR can be approved from GitHub, from the dashboard `/approvals` page, or from the CLI `agentbreeder review`. Approving in any of those updates all three.
- A configurable promotion pipeline: `dev → staging → prod`, with per-env approvers, per-env clouds, per-env registries, and per-env service principals.
- Full audit: every change has a git commit, a PR, an approver, a deploy job, and a registry mutation — all linked.
- The platform is opinionated about the flow but lets orgs override the wiring (their CODEOWNERS, their cloud accounts, their eval-gate policies).

### Non-goals (this doc)
- A bespoke git server. We use GitHub.
- Replacing CODEOWNERS with a homegrown approver model. We *augment* CODEOWNERS with `team.approvers` and ResourcePermission ACLs but never replace it.
- Cross-env data migration (e.g. copying RAG indexes from staging to prod). That is its own design.
- Multi-region active-active. v2.x is single-region per env.

---

## 3. The end-to-end flow

```
User                  AgentBreeder API           GitHub                 Cloud (AWS / GCP / Azure)        Per-env Registry
 │                          │                       │                            │                               │
 │── Save in builder ──────▶│                       │                            │                               │
 │                          │── PR draft (HTTP) ───▶│                            │                               │
 │                          │   commit on agent/X   │                            │                               │
 │                          │   branch              │                            │                               │
 │                          │                       │                            │                               │
 │── Submit for review ────▶│                       │                            │                               │
 │                          │── PR ready, label ───▶│                            │                               │
 │                          │   `agent:dev`         │                            │                               │
 │                          │   reviewers from      │                            │                               │
 │                          │   team policy         │                            │                               │
 │                          │                       │                            │                               │
 │                          │  /approvals page ◀────┤  PRs filtered by ACL       │                               │
 │                          │                       │                            │                               │
Approver                    │                       │                            │                               │
 │── Approve in dashboard ─▶│                       │                            │                               │
 │                          │── approveReviews ────▶│                            │                               │
 │                          │── auto-merge (if ────▶│                            │                               │
 │                          │   policy allows)      │                            │                               │
 │                          │                       │                            │                               │
 │                          │◀── webhook on merge ──┤                            │                               │
 │                          │                       │                            │                               │
 │                          │── deploy to dev ─────────────────────────────────▶ │                               │
 │                          │                                                    │                               │
 │                          │◀── deploy succeeded ───────────────────────────────┤                               │
 │                          │── update dev registry ──────────────────────────────────────────────────────────▶  │
 │                          │                                                    │                               │
 │── Promote to staging ───▶│                                                    │                               │
 │                          │── (env-gate: 1-of-N approver, eval pass) ─────────▶│                               │
 │                          │── deploy to staging ─────────────────────────────▶ │                               │
 │                          │── update staging registry ──────────────────────────────────────────────────────▶  │
 │                          │                                                    │                               │
 │── Promote to prod ──────▶│                                                    │                               │
 │                          │── (env-gate: 2-of-N approver, eval pass, soak) ───▶│                               │
 │                          │── deploy to prod ────────────────────────────────▶ │                               │
 │                          │── update prod registry ─────────────────────────────────────────────────────────▶  │
```

The user's mental model never leaves "I clicked save, then I asked for review, then it shipped." All the cross-system mechanics are platform concerns.

---

## 4. Component design

### 4.1 Workspace = GitHub repo (formal binding)

A *workspace* binds 1:1 to a GitHub repository. The workspace record (existing `engine.secrets.workspace.WorkspaceSecretsConfig`, extended for v2.2) gets:

```yaml
workspace: customer-success
github:
  repo: org/customer-success-agents
  default_branch: main
  installation_id: 12345        # GitHub App install id
  branch_template: "agent/{name}/v{version}"
secrets:
  backend: aws
  options: { region: us-east-1 }
environments:
  - name: dev
    cloud: aws
    region: us-east-1
    deployer_service_account: arn:aws:iam::111111111111:role/agentbreeder-dev
    registry_url: postgres://.../registry_dev
    auto_deploy_on_merge: true
    approvers:
      min_count: 0
  - name: staging
    cloud: gcp
    region: us-central1
    deployer_service_account: agentbreeder-staging@project.iam.gserviceaccount.com
    registry_url: postgres://.../registry_staging
    auto_deploy_on_merge: false
    approvers:
      min_count: 1
      teams: [team:engineering]
  - name: prod
    cloud: aws
    region: us-east-1
    deployer_service_account: arn:aws:iam::222222222222:role/agentbreeder-prod
    registry_url: postgres://.../registry_prod
    auto_deploy_on_merge: false
    approvers:
      min_count: 2
      teams: [team:engineering, team:security]
      eval_gate:
        min_pass_rate: 0.95
        suite: production-readiness
      soak_period: 6h
```

Storage: this lives in `.agentbreeder/workspace.yaml` on the repo's `main` branch (single source of truth) AND mirrored to the API's DB for fast reads. The mirror is refreshed on every push to `main`.

### 4.2 Create flow (CLI, IDE, dashboard all push to git)

**CLI** (already exists): `agentbreeder submit` makes the commit and PR.

**IDE / SDK**: `Agent.save()` in the SDK does an HTTP `POST /api/v1/git/branches` with the diff. The API uses the GitHub App installation token to commit; returns `{ branch, pr_number, dashboard_url }`.

**Dashboard** (NEW for this work): every builder grows a "Save & Submit" button next to its existing "Save". Behavior:

- `Save` (existing) → POST to the API's draft store (so the user can iterate without committing). Stored in `agent_drafts` table keyed by `(user_id, agent_name)`. Auto-saved every 30s.
- `Save & Submit` → POST `/api/v1/git/submit` with the draft's content. Backend:
   1. Computes the diff against `main`
   2. Creates branch `agent/<name>/v<version>` via GitHub App
   3. Commits the YAML(s) and any code blob
   4. Opens a PR with title `[agent] <name> v<version>` and body auto-generated from the diff
   5. Adds label `agent:dev` (initial gate)
   6. Adds reviewers from `team.approvers` (workspace.yaml) + CODEOWNERS
   7. Drops the row from `agent_drafts`
   8. Returns `pr_number, pr_url`

Same flow for prompts (`prompt:dev`), tools (`tool:dev`), MCPs (`mcp:dev`), RAG (`rag:dev`), evals (`eval:dev`).

The dashboard `/approvals` page shows PRs not internal queue rows.

### 4.3 Approval queue = PR queue (unification)

Today: `approval_queue` table stores rows for "things needing approval"; `/approvals` page reads it.

After: `approval_queue` becomes a *cache* of GitHub PR review state, keyed by `(repo, pr_number)`. Backed by:

```sql
CREATE TABLE pr_approval_state (
  repo            VARCHAR(255) NOT NULL,
  pr_number       INTEGER NOT NULL,
  artifact_kind   VARCHAR(20) NOT NULL,   -- agent | prompt | tool | mcp | rag | eval
  artifact_name   VARCHAR(255) NOT NULL,
  artifact_version VARCHAR(50),
  required_approvers INTEGER NOT NULL,
  current_approvals  INTEGER NOT NULL,
  approver_emails    TEXT[],
  github_status      VARCHAR(20),         -- open | approved | merged | closed
  last_synced_at     TIMESTAMPTZ,
  PRIMARY KEY (repo, pr_number)
);
```

Sync via GitHub webhook (preferred — instant) and a 60s reconciliation cron (fallback). Both write to this table.

The dashboard `/approvals` page reads from this table joined with `agent_drafts`/PR metadata.

**Approve button** behavior:
1. Calls GitHub API `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` with `event: APPROVE`
2. Increments `current_approvals` in the local cache
3. If `current_approvals >= required_approvers`, merges the PR (squash) via GitHub API
4. Webhook receives the merge event and triggers the dev-env deploy

### 4.4 Approver derivation

The set of valid approvers for a PR is computed at PR-open time:

1. **CODEOWNERS** (already in repo): GitHub's primary mechanism. AgentBreeder respects it.
2. **`team.approvers`** from workspace.yaml: a list of usernames per team. Augments CODEOWNERS for domain-specific approvers (e.g. data-science-team approves anything touching `prompts/`).
3. **ResourcePermission ACL rows**: per-resource approvers. E.g. `agents/customer-support` might require alice@ regardless of which team submits the PR.
4. **Eval gate** (env-level): if the env's `eval_gate.min_pass_rate` is set, the deploy is blocked until an eval run posts a status check ≥ that threshold.

Validity check: an approval counts if the approver appears in **at least one** of the above. The approver does NOT need to be in all of them.

### 4.5 Multi-env promotion

After PR merge to `main`:

- The webhook triggers `dev` deploy if `auto_deploy_on_merge: true` (default for dev).
- Promotion to `staging` requires:
   - 1+ approval (per env config)
   - Eval gate (if configured)
   - User explicitly clicking `Promote → staging` in the dashboard or `agentbreeder promote --env staging`
- Promotion to `prod` requires:
   - 2+ approvals from `team:security` + `team:engineering`
   - Production-readiness eval pass
   - 6h soak (configurable) on staging without an alert
   - Explicit `Promote → prod`

A `promotions` table tracks the state of each artifact's environment progression:

```sql
CREATE TABLE promotions (
  id              UUID PRIMARY KEY,
  artifact_kind   VARCHAR(20) NOT NULL,
  artifact_name   VARCHAR(255) NOT NULL,
  artifact_version VARCHAR(50) NOT NULL,
  source_pr       INTEGER,
  source_commit   VARCHAR(40),
  env             VARCHAR(50) NOT NULL,
  state           VARCHAR(20) NOT NULL,       -- pending | approved | deploying | deployed | failed | rolled_back
  approver_emails TEXT[],
  promoted_by     VARCHAR(255),
  deploy_job_id   UUID,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  completed_at    TIMESTAMPTZ
);
```

The dashboard grows an "Environments" column on `/agents`, `/prompts`, etc. — three pills (`dev ✓ • staging — • prod ✗`) per row, clickable to drill into the promotion state.

### 4.6 Per-env registry

Each environment has its own Postgres database. The deployer writes to the env's registry on successful deploy with:

```python
await EnvRegistry.upsert(
    env="prod",
    artifact=AgentArtifact(
        name=config.name,
        version=config.version,
        framework=config.framework,
        config_snapshot=config.model_dump(),
        git_ref=os.environ["GITHUB_SHA"],         # commit SHA from CI
        deployed_by=actor_email,
        deployed_at=datetime.now(UTC),
        cloud=env.cloud,
        endpoint_url=deploy_result.endpoint_url,
    ),
)
```

The dashboard reads from one env's registry at a time (env selector in the topbar). Switching env switches the data source.

### 4.7 Per-env service principals (cloud creds)

Each env in `workspace.yaml` declares a `deployer_service_account`. The API server has zero direct cloud creds; it assumes the env's role at deploy time:

- AWS: STS `AssumeRole` with `RoleArn = arn:aws:iam::222222222222:role/agentbreeder-prod`
- GCP: short-lived service-account-impersonation token via the platform's service account
- Azure: federated identity through the API's managed identity

This means: leaking the API server's runtime creds does not give attackers prod cloud access. Each promotion explicitly pulls the right env's role.

The role is provisioned via Pulumi/Terraform (separate from this doc), and its trust policy says: "trust the AgentBreeder API server's principal AND require an external session id derived from the PR number to prevent replay."

### 4.8 GitHub App vs PAT vs OAuth

The API server authenticates to GitHub as a **GitHub App** (not a PAT, not OAuth as user). Per-workspace GitHub App installations give:

- A scoped installation token (per-org, per-repo)
- The ability to commit/PR/merge as `agentbreeder[bot]`
- Webhook events for PR reviews, merges, and pushes
- Organization-level audit attribution

Users authenticate to AgentBreeder via OAuth (or whatever the existing AuthProvider does); their user identity is recorded as the `actor_email` on every action, but the *GitHub commit* is `agentbreeder[bot]` with `Co-authored-by: <actor_email>`.

---

## 5. Migration plan from v2.1 → v2.2

We don't need to ship all of this at once. Phased plan:

### Phase 1 — git-backed workspace (closes #146 substantially)
- Workspace YAML schema
- GitHub App skeleton (install URL on `/settings/integrations`, callback)
- API endpoints `/api/v1/git/branches` (create), `/api/v1/git/submit` (open PR)
- Dashboard "Save & Submit" button on `/agents/builder`, `/prompts/builder`, `/tools/builder`
- The `agent_drafts` table for dashboard auto-save

### Phase 2 — approval queue ↔ PR queue
- `pr_approval_state` table + migration
- GitHub App webhook handler (`/api/v1/webhooks/github`)
- Refactor `/approvals` page to read PRs
- Approver derivation rules (CODEOWNERS + workspace.yaml + ACL)

### Phase 3 — multi-env promotion (closes #147 substantially)
- `promotions` table + migration
- `agentbreeder promote --env <name>` CLI
- Dashboard Promote button + env pills on every artifact list page
- Eval gate hook (read eval status check on PR; block promote if below threshold)

### Phase 4 — per-env registry
- Refactor `AgentRegistry`/etc. to take an `env` parameter; add a `EnvRegistry` factory
- Migration to add `git_ref` + `deployed_by` columns to existing registry tables
- Dashboard env-selector in topbar
- Cross-env diff view (compare prod vs staging for any artifact)

### Phase 5 — per-env service principals
- AWS STS / GCP impersonation / Azure FIC integration in deployers
- `deployer_service_account` field reading
- Audit event on every assume

Each phase is 1-3 PRs; the full plan is roughly v2.2 + v2.3 + v2.4.

---

## 6. Open questions

1. **Eval gate timing.** Eval runs are themselves agents. Do we wait synchronously on a PR check, or async-poll? Probably async with a configurable timeout (default 30min).
2. **CODEOWNERS vs workspace.yaml conflict.** Whose approver list wins when both apply? Proposal: `union` (either may approve), but a `strict_codeowners: true` flag in `workspace.yaml` enforces CODEOWNERS-only.
3. **Rollback semantics.** A failed prod deploy should auto-rollback. Where does the *previous* version come from? Proposal: the previous successful row in `promotions` for the same `(artifact_kind, artifact_name, env)`.
4. **PR description auto-generation.** The platform-generated PR body should include a human-readable diff (model swap, tool added, etc). Implementation TBD — likely a small templating layer that compares the previous and new YAML tree.
5. **Service-principal bootstrap.** Org admins need to create the per-env IAM roles. We should ship a bootstrap CLI (`agentbreeder workspace init --env prod --cloud aws --account 222222222222`) that prints the trust policy + required IAM statements rather than running them — clarity over magic.
6. **Drafts sharing.** Today `agent_drafts` is keyed by user. Two PMs collaborating on the same agent need a shared draft. Defer to v2.3 — initial implementation is single-user drafts, "share" button creates the PR earlier.

---

## 7. What exists today that we keep

| Primitive | Status | Reuse |
|---|---|---|
| `cli/commands/submit.py` | Shipped | Wire its logic into the new API endpoint |
| `cli/commands/review.py` | Shipped | Add a flag for `--env staging` to gate promotions |
| `cli/commands/publish.py` | Shipped | Becomes the `--env` promote command |
| `api/routes/git.py` | Shipped | Extend with `/branches`, `/submit`, `/promote` |
| `api/routes/approvals.py` | Shipped | Refactor backing store to `pr_approval_state` |
| Migration 015 (RBAC + ACL + service principals) | Shipped | Approver derivation reads ResourcePermission |
| Deployers (ECS, Cloud Run, ACA, K8s, App Runner) | Shipped | Add per-env service-account assumption |
| `IncidentService` (#207) | Shipped | A failed prod deploy auto-creates an Incident |
| `ComplianceService` (#208) | Shipped | A scheduled compliance scan blocks prod promotes if controls regress |

The whole v2.0/v2.1 substrate is reused. v2.2 is **glue and governance**, not new primitives.

---

## 8. Out of scope for this doc

- Full FedRAMP / SOC2 audit-trail formalization (separate doc; the compliance scanner shipped in #208 is the foundation but the formal control mapping is a different effort).
- Multi-org tenancy (this doc assumes a single AgentBreeder install per org).
- Automated cost-budget gating per env (separate, builds on v2.0 budget primitives).
- A2A authorization flows when an agent in env-A calls an agent in env-B.

---

## Appendix A — Summary of touched DB schemas

| Table | Status | Change |
|---|---|---|
| `workspaces` | NEW | Workspace metadata + GitHub App install id |
| `agent_drafts` | NEW | Per-user dashboard draft store |
| `pr_approval_state` | NEW | Cache of GitHub PR review state |
| `promotions` | NEW | Per-env promotion state |
| `agents` | MODIFIED | Add `git_ref`, `deployed_by`, `env` columns; add unique on `(env, name, version)` |
| `prompts` | MODIFIED | Same as agents |
| `tools` | MODIFIED | Same as agents |
| `mcp_servers` | MODIFIED | Same as agents |
| `audit_events` | EXISTING | Receive new event types: `pr.opened`, `pr.merged`, `promotion.requested`, `promotion.completed` |

Appendix B — see `engine/schema/workspace.schema.json` (to be added in Phase 1).
