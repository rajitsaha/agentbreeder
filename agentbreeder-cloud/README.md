# AgentBreeder Cloud

> Managed cloud platform built on top of the open-source AgentBreeder core.
> The enterprise-grade, zero-ops way to run AgentBreeder without managing your own infrastructure.

---

## What is AgentBreeder Cloud?

AgentBreeder Cloud is the hosted version of AgentBreeder. The same open-source deploy pipeline, registry, and governance — but running on AgentBreeder's infrastructure so your team doesn't have to manage it.

**Open-source AgentBreeder:** You bring your own AWS/GCP/Azure. You manage the platform.
**AgentBreeder Cloud:** You bring your agents. We manage everything else.

---

## Planned Feature Scope

### Platform
- Managed AgentBreeder API, registry, and dashboard (multi-region)
- GitHub-connected deployments with automatic rollback
- Managed PostgreSQL + Redis (no database ops)
- Built-in TLS, custom domains, and VPN peering options

### Enterprise Features
- SSO / SAML 2.0 (Okta, Azure AD, Google Workspace)
- Advanced RBAC with attribute-based access control (ABAC)
- Downloadable SOC2 Type II and HIPAA compliance evidence packs
- Data residency controls (US, EU, APAC regions)
- 99.9% uptime SLA with dedicated support

### Billing & Metering
- Subscription tiers (Starter, Teams, Enterprise)
- Usage-based metering for agent invocations
- Cost pass-through at cost (no markup on your cloud spend)
- Per-team chargeback reporting

### Managed Observability
- Auto-injected OpenTelemetry sidecar (no agent code changes)
- Hosted Grafana dashboards for fleet metrics
- 90-day trace retention (configurable)
- Anomaly alerting via PagerDuty / Slack / email

---

## Directory Structure

```
agentbreeder-cloud/
├── README.md           # This file
├── ROADMAP.md          # Cloud-specific release plan
├── docs/
│   ├── architecture.md # Cloud platform architecture
│   ├── pricing.md      # Tier pricing and metering model
│   └── features.md     # Full enterprise feature list
├── api/                # Cloud-specific API extensions (billing, SSO, compliance)
├── infra/              # IaC for the managed platform (Pulumi)
└── billing/            # Subscription and metering logic
```

---

## Relationship to Open Source

AgentBreeder Cloud is **additive** — it does not fork or diverge from the open-source core.

```
agentbreeder (open source, Apache 2.0)
    +
agentbreeder-cloud (commercial extensions)
    =
AgentBreeder Cloud Platform
```

All core platform improvements developed for the cloud product are contributed back to the open-source repo. The cloud product adds managed infrastructure, enterprise auth, compliance tooling, and billing — not capability forks.

---

## Status

**Pre-development.** This directory is the planning foundation for AgentBreeder Cloud. See `docs/` for architecture and pricing decisions as they are made.
