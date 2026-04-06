# The Agent-Revenue Stack: What Nobody Is Telling You

*By Rajit Saha — Director of Data & ML Platform Architecture*

---

1.5 million corporate AI agents are running right now with no RBAC, no cost attribution, and no audit trail.

Your finance team will ask about this. Your CISO will ask about this. Your board will ask about this.

Do you have an answer?

I didn't. And I've been building data infrastructure since Yahoo was still relevant.

---

## I Solved the Wrong Problem for 20 Years

I've built data platforms at Yahoo, VMware, LendingClub, Experian, and Udemy. Five companies. Two decades. Petabytes of data moved, cleaned, governed, and served.

At every one of those companies, I walked into budget cycles defending my team's existence. "What does the data platform actually produce?" The answer was always indirect. Faster dashboards. Cleaner reports. Better models. The value was real. The connection to revenue was invisible.

Six months ago, I published a piece about what I finally understood after 20 years: data platforms have been designed around the wrong question. We asked "how do we store and move data efficiently?" when we should have been asking "what revenue does this data create — and can an agent act on it today?"

The response surprised me. Thousands of data leaders, ML engineers, and CTOs shared it. They felt it too. The frustration of building infrastructure that can't prove its worth.

But then something unexpected happened.

After I published that piece, I had a problem. The platform design was right. The agents weren't — not because of the models, but because there was no standard way to deploy, govern, or track them at scale.

I had built the runway. Nobody had built the plane.

---

## Agent Sprawl Is Already Here

Let me tell you what I'm seeing in 2026.

Every engineering team is deploying agents. Some are using LangGraph. Some are using OpenAI's SDK. Some are using Claude. Some are using CrewAI. Most are using whatever the senior engineer on their team happened to learn last quarter.

Each agent is deployed differently. Some live in Docker containers someone manually SSH'd into. Some are serverless functions with no logging. Some are running on a developer's laptop in a tmux session that's been up for three weeks.

Nobody knows:
- What agents exist in their organization
- What each agent costs to run
- Who approved them for production
- What data they're accessing
- What happens when they fail

This is shadow IT 2.0. And it's moving 100x faster than the shadow IT of the 2010s because agents can take actions. They don't just read data — they write to it, call APIs with it, make decisions with it.

The industry has a name for this now: **agent sprawl**. 88% of organizations reported security incidents from unmanaged agents in 2025. The average cost per breach: $4.6M.

We've seen this movie before. We saw it with unmanaged data pipelines in 2012. We saw it with unmanaged microservices in 2017. Every time, the answer was the same: **governance has to be built into the deployment layer, not bolted on afterward.**

We didn't learn. We're doing it again.

---

## The Stack Nobody Has Drawn

Here's what a production AI agent actually requires. Nobody is drawing this diagram.

```
┌─────────────────────────────────────────┐
│           REVENUE OUTCOMES              │  ← What the business cares about
├─────────────────────────────────────────┤
│         AGENT OPERATIONS LAYER          │  ← Deploy · Govern · Observe · Cost-track
│   (The layer that doesn't exist yet)    │
├─────────────────────────────────────────┤
│     AGENT FRAMEWORKS & RUNTIMES         │  ← LangGraph, CrewAI, Claude SDK, OpenAI
├─────────────────────────────────────────┤
│      AGENT-READY DATA PLATFORM          │  ← Low-latency, semantic, self-describing
├─────────────────────────────────────────┤
│         CLOUD INFRASTRUCTURE            │  ← AWS, GCP, Azure
└─────────────────────────────────────────┘
```

The top layer (revenue outcomes) and the bottom layers (data platform, cloud infra, agent frameworks) have dozens of tools and vendors. The middle layer — Agent Operations — has almost nothing.

The frameworks give you the building blocks. The cloud gives you the compute. The data platform gives you the context. But nobody is providing the layer that takes an agent from "works on my laptop" to "running in production with RBAC, cost attribution, audit trail, and org-wide discoverability."

That's the missing layer. And its absence is why 95% of agent projects never reach production.

Let me be precise about what this layer needs to do:

**1. Governance must be a side effect of deploying — not extra configuration.**

Every time a developer deploys an agent, RBAC should be validated automatically. An audit log entry should be written automatically. The agent should be registered in an org-wide catalog automatically. Cost should be attributed to the deploying team automatically.

Not because someone remembered to configure it. Because the deployment pipeline cannot complete without it.

**2. Framework agnosticism is non-negotiable.**

Your company will not standardize on one agent framework. It never happened with databases. It never happened with message queues. It won't happen with agent SDKs either. The operations layer has to work with all of them.

**3. Multi-cloud is table stakes for enterprises.**

AWS AgentCore is excellent — if you're willing to run only Bedrock models on AWS forever. Google Vertex AI Agent Engine is excellent — if you want GCP lock-in and Gemini only. Enterprises are not willing to make that bet. They want the operational layer to be cloud-neutral.

**4. The registry is the product.**

I say this as someone who spent 20 years building data platforms: the catalog is the thing. The governance features of a data platform are only as good as its registry — who can see what, who owns what, what depends on what. Agent platforms are the same. An org-wide agent registry with discoverability, versioning, ownership, and lineage is the actual enterprise value.

---

## The Category I'm Proposing: Agent Revenue Operations

Here's the thesis I've been building toward for 20 years without knowing it.

DataOps solves the data pipeline problem. MLOps solves the model lifecycle problem. LLMOps solves the prompt and evaluation problem. AgentOps solves the agent monitoring problem.

But none of them answer the question that actually matters: **how does this connect to company revenue?**

I'm proposing a new category. Call it **Agent Revenue Operations** — the discipline of deploying, governing, and operating AI agents in a way that creates a measurable, auditable, direct line from your data platform to business outcomes.

This isn't a technology category. It's a business discipline.

The data platform is the foundation. The agent is the actuator. The governance layer is what makes it enterprise-safe. And the revenue connection is what makes it worth funding.

The companies that figure out how to build this stack — data platform → agent runtime → governance layer → revenue outcome — will have a moat that's genuinely hard to copy. Not because the technology is secret. Because the organizational muscle to run it takes years to build.

---

## What I Built

I got tired of waiting for someone else to build the Agent Operations layer. So I built it.

It's called **AgentBreeder**. It's open source.

The core idea: a developer writes one `agent.yaml` file, runs `agentbreeder deploy`, and their agent is live on AWS or GCP — with RBAC, cost tracking, audit trail, and org-wide discoverability automatic. Zero extra configuration. Governance is a side effect of deploying.

It's framework-agnostic. LangGraph, CrewAI, Claude SDK, OpenAI Agents SDK, Google ADK — they all deploy through the same pipeline. The pipeline doesn't know which framework produced the config. This is intentional.

It's multi-cloud. Not AWS-only. Not GCP-only. Any framework, any cloud, one command.

It has three builder tiers for teams at different skill levels — a visual drag-and-drop UI for PMs and analysts, YAML configuration for ML engineers, and a full Python/TypeScript SDK for senior engineers who need programmatic control. All three compile to the same deployment format. All three get the same governance.

And it has an org-wide registry. The thing I missed for 20 years. A catalog of every agent in your organization — who owns it, what it costs, what it does, what data it touches, who can call it.

The managed cloud service is coming. But right now it's open source and I want feedback from the people building this category with me.

---

## What I'm Asking From You

I've been in data infrastructure long enough to know that the tools don't win. The communities do.

dbt didn't win because it was the best SQL tool. It won because it built a community of analytics engineers who changed how the industry thought about data transformation. Hashicorp didn't win on technical merit alone. It won because it defined what "infrastructure as code" meant before anyone else did.

I'm trying to do the same thing for agent operations.

If you're a data leader, ML engineer, CTO, or VP Engineering who has tried to take agents to production and hit the governance wall — I want to hear from you. What broke? What was missing? What did you have to build yourself?

If you're a VC or executive trying to understand where the durable value in the AI agent ecosystem lives — I think it's here. In the operations and governance layer. Not in the models. Not in the frameworks. In the layer that connects the agent to the enterprise safely and at scale.

The frameworks are the lego bricks. AgentBreeder is the instruction manual and the quality control. And the category we're building — Agent Revenue Operations — is the reason enterprises will pay for it.

We're at the beginning of this. Join me.

**→ GitHub: github.com/agentbreeder/agentbreeder**
**→ I read every comment and reply to most of them.**

---

*Rajit Saha is Director of Data & ML Platform Architecture at Udemy. He has spent 20+ years building data infrastructure at Yahoo, VMware, LendingClub, Experian, and Udemy. AgentBreeder is his open-source answer to the agent operations problem.*
