# API Stability & Versioning

AgentBreeder follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

---

## Stability tiers

| Tier | Guarantee | Where |
|---|---|---|
| **Stable** | No breaking changes within a major version | `agent.yaml` schema, CLI flags, REST API `/v1/` |
| **Beta** | May change in minor versions; deprecation notice given one release early | REST API `/v2/`, SDK orchestration API |
| **Experimental** | Can change at any time | `engine/` internals, `--experimental` CLI flags |

---

## REST API versioning

All stable endpoints are prefixed `/api/v1/`. When breaking changes are required, a new prefix is introduced (`/api/v2/`) and the old version is deprecated with a `Deprecation` response header. Old versions remain supported for at least two minor releases.

```
Deprecation: version="v1", date="2026-10-01"
Sunset: Mon, 01 Oct 2026 00:00:00 GMT
Link: <https://docs.agentbreeder.io/migrations/>; rel="successor-version"
```

---

## `agent.yaml` schema versioning

The `agent.yaml` schema is versioned independently. Additive changes (new optional fields) are made in minor releases. Removals and renames are made only in major releases with a migration guide in [`docs/migrations/`](migrations/OVERVIEW.md).

---

## CLI versioning

Check your installed version:

```bash
agentbreeder --version
```

CLI commands and flags marked `(beta)` in `--help` output may change in minor versions. All other flags are stable.

---

## Deprecation policy

1. Deprecated features are announced in the [CHANGELOG](https://github.com/agentbreeder/agentbreeder/blob/main/CHANGELOG.md)
2. A deprecation warning is emitted at runtime for at least one minor release
3. The feature is removed in the next major version

---

## Upgrade guides

See [Migrations](migrations/OVERVIEW.md) for step-by-step upgrade instructions between major versions.
