# /model-e2e-test — End-to-End Model Verification Pipeline

> Verifies an AgentBreeder agent end-to-end: local stack → registries → cloud deploy → live LLM call.
>
> **Trigger:** `/model-e2e-test [<agent-dir>] [<cloud-target>]`
>
> **Defaults:** agent-dir = `microlearning-ebook-agent`, cloud-target = `gcp` (Cloud Run, us-central1).

You are a verification engineer. Execute each phase in order. Each must fully complete before advancing. Stop only on a gate that's truly unfixable. Bake in **every gotcha** discovered during the manual walkthrough that produced this skill.

---

## Phase 0 — Stack readiness

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
```

### 0a. Source `.env` so docker-compose env-substitution works

The compose file uses `${GOOGLE_API_KEY:-}` etc. Without an env source, the API container starts with empty keys and `/playground` returns "no model available."

```bash
AGENT_DIR="${1:-microlearning-ebook-agent}"
[ -f "$AGENT_DIR/.env" ] && set -a && source "$AGENT_DIR/.env" && set +a
# Always ensure GOOGLE_API_KEY (litellm gateway needs it)
[ -z "${GOOGLE_API_KEY:-}" ] && { echo "ERR: GOOGLE_API_KEY missing in $AGENT_DIR/.env"; exit 1; }
export GOOGLE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
```

### 0b. Bring up the stack

```bash
docker compose -f deploy/docker-compose.yml up -d --build postgres redis api dashboard litellm
```

If port 6379 is already taken (common — another project's redis): `docker stop $(docker ps --filter publish=6379 -q | head -1)` and re-up.

### 0c. Apply migrations — **MUST run after litellm starts**

LiteLLM's prisma migrations write to the same database and corrupt the agentbreeder schema (the `users` table disappears). Always re-run alembic AFTER litellm has settled:

```bash
docker compose -f deploy/docker-compose.yml run --rm migrate
```

If you see `relation "users" does not exist` later, this step was skipped or LiteLLM ran a fresh prisma migration against the shared DB. The fix in `deploy/docker-compose.yml` sets `STORE_MODEL_IN_DB: False` to prevent this — verify it's still set.

### 0d. Wait for ready

```bash
until curl -sf http://localhost:8000/health | grep -q healthy; do sleep 2; done
until curl -sf http://localhost:3000/ -o /dev/null 2>/dev/null || curl -sf http://localhost:3001/ -o /dev/null 2>/dev/null; do sleep 2; done
until curl -sf http://localhost:4000/health/liveliness >/dev/null 2>&1; do sleep 2; done
```

**GATE:** `/health` on port 8000 returns `{"status":"healthy"}`, dashboard responds 200, LiteLLM responds 200.

---

## Phase 1 — Auth + RBAC

### 1a. Register a verification user

```bash
EMAIL="e2e-$(date +%s)@example.com"   # NOT @test.local — pydantic email-validator rejects reserved TLDs
PASSWORD="E2EVerify123!"

curl -sf -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"name\":\"E2E\"}" >/dev/null
```

### 1b. Promote to deployer (default role is `viewer`, which can't add providers/agents)

```bash
docker compose -f deploy/docker-compose.yml exec -T postgres \
  psql -U agentbreeder -d agentbreeder \
  -c "UPDATE users SET role='deployer' WHERE email='$EMAIL';"
```

### 1c. Login and capture JWT

```bash
TOKEN=$(curl -sf -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
[ -n "$TOKEN" ] || { echo "ERR: no JWT"; exit 1; }
```

**GATE:** Token length > 100 chars.

---

## Phase 2 — Registry verification (Track F + K + agents)

```bash
# Track F: provider catalog (must show 9 OpenAI-compatible presets)
COUNT=$(curl -sf "http://localhost:8000/api/v1/providers/catalog" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']))")
[ "$COUNT" -ge 9 ] || { echo "ERR: provider catalog has $COUNT entries (expected ≥9)"; exit 1; }

# Track K: secrets (empty list is fine; 500 means INSTALL_MODE wasn't set to `team`)
curl -sf "http://localhost:8000/api/v1/secrets" -H "Authorization: Bearer $TOKEN" >/dev/null \
  || { echo "ERR: /secrets failing — set AGENTBREEDER_INSTALL_MODE=team in compose api env"; exit 1; }

# Agents registry
curl -sf "http://localhost:8000/api/v1/agents" -H "Authorization: Bearer $TOKEN" >/dev/null

# Other registries
for r in prompts tools mcp_servers; do
  curl -sf "http://localhost:8000/api/v1/$r" -H "Authorization: Bearer $TOKEN" >/dev/null \
    || echo "  ⚠ /api/v1/$r unreachable"
done
```

**GATE:** Track F returns ≥9 catalog entries; Track K returns 200 (empty list ok); agents endpoint reachable.

---

## Phase 3 — Validate every example agent

```bash
PASS=0; FAIL=0
for ex in examples/*/; do
  for y in "$ex"agent.yaml "$ex"*/agent.yaml; do
    [ -f "$y" ] || continue
    if python3 -m cli.main validate "$y" >/dev/null 2>&1; then
      PASS=$((PASS+1))
    else
      echo "  ✗ $y"
      FAIL=$((FAIL+1))
    fi
  done
done
echo "validation: $PASS pass, $FAIL fail"
```

**GATE:** PASS ≥ 19. (Some templates have known schema issues — track them but don't block the pipeline.)

---

## Phase 4 — Local deploy smoke

Deploy one fast-validating agent and smoke its `/health`:

```bash
export AGENTBREEDER_API_TOKEN="$TOKEN"   # so the deploy → registry sync works
python3 -m cli.main deploy examples/langgraph-agent/agent.yaml --target local
sleep 3

# Find the assigned port from the deploy output (or docker ps)
LOCAL_PORT=$(docker ps --filter "name=agentbreeder-" --format "{{.Ports}}" | grep -oE '0\.0\.0\.0:[0-9]+' | cut -d: -f2 | head -1)
[ -n "$LOCAL_PORT" ] && curl -sf "http://localhost:$LOCAL_PORT/health" | head -c 200
```

**GATE:** A container with name `agentbreeder-*` is healthy and `/health` returns `{"status":"healthy"}`.

---

## Phase 5 — Cloud deploy (target: $CLOUD_TARGET, default `gcp`)

### 5a. Tear down any existing deployment with the same name

```bash
SERVICE="$AGENT_DIR"   # by convention, agent name == service name
case "${2:-gcp}" in
  gcp)
    if gcloud run services describe "$SERVICE" --region=us-central1 >/dev/null 2>&1; then
      gcloud run services delete "$SERVICE" --region=us-central1 --quiet
    fi
    ;;
  aws)
    aws ecs delete-service --cluster agentbreeder --service "$SERVICE" --force 2>/dev/null || true
    ;;
esac
```

### 5b. Run the agent's deploy script (preferred over `agentbreeder deploy --target gcp` if the agent ships a custom script)

```bash
if [ -f "$AGENT_DIR/scripts/deploy_${CLOUD_TARGET:-gcp}.sh" ]; then
  bash "$AGENT_DIR/scripts/deploy_${CLOUD_TARGET:-gcp}.sh" 2>&1 | tee /tmp/abe2e-deploy.log
else
  python3 -m cli.main deploy "$AGENT_DIR/agent.yaml" --target "${CLOUD_TARGET:-gcp}" 2>&1 | tee /tmp/abe2e-deploy.log
fi
```

### 5c. Discover the deployed URL

```bash
case "${2:-gcp}" in
  gcp)
    SERVICE_URL=$(gcloud run services describe "$SERVICE" --region=us-central1 --format="value(status.url)")
    ;;
esac
[ -n "$SERVICE_URL" ] || { echo "ERR: no service URL"; exit 1; }
```

**GATE:** Cloud-build status `SUCCESS`; service URL non-empty.

---

## Phase 6 — Live LLM smoke against the deployed agent

### 6a. Health (no auth)

```bash
curl -sf "$SERVICE_URL/health" | grep -q healthy || { echo "ERR: cloud /health failing"; exit 1; }
```

### 6b. Auth gate (must reject without bearer)

```bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVICE_URL/invoke" \
  -H "Content-Type: application/json" -d '{"input":"hi"}')
[ "$STATUS" = "401" ] || { echo "ERR: invoke without auth returned $STATUS, expected 401"; exit 1; }
```

### 6c. Live invocation (real LLM call)

```bash
# CAREFUL: parse .env without inheriting comment lines
AGENT_AUTH_TOKEN=$(grep -E "^AGENT_AUTH_TOKEN=" "$AGENT_DIR/.env" | cut -d= -f2-)
[ -n "$AGENT_AUTH_TOKEN" ] || { echo "ERR: AGENT_AUTH_TOKEN missing in $AGENT_DIR/.env"; exit 1; }

RESP=$(curl -sf -X POST "$SERVICE_URL/invoke" \
  -H "Authorization: Bearer $AGENT_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input":"Say hi in 5 words"}' --max-time 180)

echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('output'), 'empty output'; print('  →', d['output'][:120])"
```

**GATE:** `/health` 200 + `/invoke` 401 without auth + `/invoke` returns non-empty `output` field with auth.

---

## Phase 6.5 — Artifact / download verification (when the agent advertises tools)

If the agent's `agent.yaml` declares any tool that produces a downloadable artifact (PDF, markdown, zip, etc.) — typically `markdown_writer`, `pdf_writer`, `ebook_generator`, or anything in `engine/tools/standard/*` whose output schema has a `download_url` or `artifact_path` field — verify the download path end-to-end.

> **Skip this phase** when `agent.yaml` has `tools: []`. The agent is text-only; there is no artifact to download. (Today, `microlearning-ebook-agent` falls into this bucket — see issue #178.)

```bash
HAS_ARTIFACT_TOOL=$(python3 -c "
import yaml
y = yaml.safe_load(open('$AGENT_DIR/agent.yaml'))
tools = y.get('tools') or []
keywords = ('writer', 'generator', 'pdf', 'ebook', 'markdown', 'export')
print('yes' if any(any(k in str(t).lower() for k in keywords) for t in tools) else 'no')
")

if [ \"$HAS_ARTIFACT_TOOL\" = \"yes\" ]; then
  # Re-invoke with a prompt that exercises the artifact tool
  ARTIFACT_RESP=$(curl -sf -X POST \"$SERVICE_URL/invoke\" \\
    -H \"Authorization: Bearer $AGENT_AUTH_TOKEN\" \\
    -H \"Content-Type: application/json\" \\
    -d '{\"input\":\"Create a 3-lesson microlearning ebook on Python decorators and return a download URL\"}' \\
    --max-time 240)

  DOWNLOAD_URL=$(echo \"$ARTIFACT_RESP\" | python3 -c \"
import sys, json, re
d = json.load(sys.stdin)
# Tools may surface the URL in different places — check structured fields first
for key in ('download_url', 'artifact_url', 'file_url'):
    if key in d:
        print(d[key]); sys.exit(0)
# Fallback: scan output text for an http(s) URL ending in .md|.pdf|.zip|.html
m = re.search(r'https?://\\\\S+\\\\.(?:md|pdf|zip|html)', d.get('output', ''))
if m: print(m.group(0))
\")

  [ -n \"$DOWNLOAD_URL\" ] || { echo \"ERR: agent has artifact tool but no download URL in response\"; exit 1; }

  # Same bearer for the artifact endpoint
  curl -fL -H \"Authorization: Bearer $AGENT_AUTH_TOKEN\" \"$DOWNLOAD_URL\" -o /tmp/abe2e-artifact.bin
  SIZE=$(wc -c < /tmp/abe2e-artifact.bin)
  [ \"$SIZE\" -gt 100 ] || { echo \"ERR: artifact suspiciously small ($SIZE bytes)\"; exit 1; }
  file /tmp/abe2e-artifact.bin
  echo \"  → artifact downloaded ($SIZE bytes)\"
fi
```

**GATE (when applicable):** download URL surfaced in invoke response → artifact retrievable with same bearer → size > 100 bytes → `file` reports a recognised type.

---

## Phase 7 — Sync the cloud URL back into the registry

The deploy → registry sync only fires when `AGENTBREEDER_API_TOKEN` is set (per builder.py). If a deploy script bypassed the engine, patch the record manually:

```bash
AGENT_RECORD_ID=$(curl -sf "http://localhost:8000/api/v1/agents" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d['data']:
    if a['name'] == '$SERVICE':
        print(a['id']); break
")

if [ -n "$AGENT_RECORD_ID" ]; then
  curl -sf -X PUT "http://localhost:8000/api/v1/agents/$AGENT_RECORD_ID" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"endpoint_url\":\"$SERVICE_URL\",\"status\":\"running\"}" >/dev/null
fi
```

**GATE:** `GET /api/v1/agents/$AGENT_RECORD_ID` shows `endpoint_url == $SERVICE_URL`.

---

## Phase 8 — Browser-loop verification (optional, manual)

Open http://localhost:3002/agents/$AGENT_RECORD_ID?tab=invoke. The Endpoint field should auto-fill with the cloud URL. Until issue #176 ships the auto-token resolver, manually paste `$AGENT_AUTH_TOKEN`. Send a message; the response in the chat panel should match the `curl /invoke` result.

> Once #176 lands, the Bearer field disappears and the user just types and hits Send.

---

## Summary output

```
=== /model-e2e-test summary ===
Agent dir:     $AGENT_DIR
Cloud target:  ${CLOUD_TARGET:-gcp}
Service URL:   $SERVICE_URL
Local stack:   ✅ healthy
Track F:       ✅ N catalog presets
Track K:       ✅ secrets reachable
Examples:      ✅ N/M validated
Local deploy:  ✅ container :PORT healthy
Cloud deploy:  ✅ build OK, URL live
Live LLM:      ✅ "<response excerpt>"
Registry sync: ✅ endpoint_url populated
Status:        VERIFIED ✅
```

---

## Gotchas captured (from the manual walkthrough that built this skill)

| Symptom | Root cause | Fix |
|---|---|---|
| `/playground` says "no model available" | API container missing GOOGLE_API_KEY / LITELLM_BASE_URL / LITELLM_MASTER_KEY | `deploy/docker-compose.yml` env block (PR #174) |
| `/api/v1/secrets` 500 with NoKeyringError | API defaulted to OS keychain inside Docker | `AGENTBREEDER_INSTALL_MODE=team` in compose api env |
| `users` table missing after `compose up` | LiteLLM's prisma migrations corrupted shared DB | `STORE_MODEL_IN_DB: False` for litellm |
| `gemini-2.5-flash` not in gateway | Not in `litellm_config.yaml` model_list | Added in PR #174 |
| Deploy → registry sync 401 | `_sync_to_api` had no Authorization header | Reads `AGENTBREEDER_API_TOKEN` env (PR #174) |
| Cloud Run `endpoint_url` empty after deploy | Script-based deploy bypasses engine sync | Patch via PUT /agents/{id} (Phase 7) |
| Bash `cut -d= -f2` truncates token at `=` chars | tokens often contain `=` | Use `cut -d= -f2-` (capture all post-`=`) |
| `@test.local` rejected by API email-validator | `.local` is RFC 6762 reserved | Use `@example.com` (RFC 2606) |
| InvokePanel field expects user JWT | Field is for `AGENT_AUTH_TOKEN`, not user JWT | Issue #176 will server-side-resolve and remove field |
| Branch protection blocks merge | required-reviews on main | `gh pr merge --admin --squash --delete-branch` |
| /models "Add provider" 403 for viewer | RBAC role default is viewer | Promote with SQL `UPDATE users SET role='deployer'` (Phase 1b) |

Each row above traces to a concrete commit on `main` or an open issue. When this skill runs and a row's symptom resurfaces, the fix is documented one click away.
