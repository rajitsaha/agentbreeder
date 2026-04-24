# AgentBreeder

**Define Once. Deploy Anywhere. Govern Automatically.**

AgentBreeder is an open-source platform for building, deploying, and governing enterprise AI agents. Write one `agent.yaml`, run `agentbreeder deploy`, and your agent is live on AWS, GCP, Azure, or locally — with RBAC, cost tracking, and an audit trail at no extra cost.

---

## Why AgentBreeder?

| Without AgentBreeder | With AgentBreeder |
|---|---|
| Wire up observability yourself | OTel traces injected automatically via sidecar |
| Configure RBAC per cloud, per agent | One `access:` block in `agent.yaml` |
| Redeploy to switch frameworks | Swap `framework:` field, redeploy |
| Track costs manually | Cost attributed to teams automatically |
| Build a discovery layer yourself | Shared org-wide registry out of the box |

---

## Install

=== "PyPI"

    ```bash
    pip install agentbreeder
    ```

=== "Homebrew"

    ```bash
    brew tap agentbreeder/agentbreeder
    brew install agentbreeder
    ```

=== "Docker"

    ```bash
    docker pull rajits/agentbreeder-cli
    ```

---

## Deploy your first agent in 60 seconds

```bash
# Run the interactive quickstart
agentbreeder quickstart

# Or start from a template
agentbreeder init my-agent --framework langgraph --model claude-sonnet-4
cd my-agent
agentbreeder deploy --target local
```

---

## Supported Frameworks & Clouds

**Frameworks:** LangGraph · CrewAI · Claude SDK · OpenAI Agents · Google ADK · Custom

**Clouds:** AWS ECS Fargate · AWS App Runner · GCP Cloud Run · Azure Container Apps · Kubernetes · Local Docker

---

## Next steps

- [Quickstart](quickstart.md) — full walkthrough with Ollama locally
- [How-To Guide](how-to.md) — recipes for every deployment target
- [CLI Reference](cli-reference.md) — every command and flag
- [agent.yaml Reference](agent-yaml.md) — complete YAML spec
