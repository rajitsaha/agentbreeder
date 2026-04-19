# Package Distribution Setup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agentbreeder release` produce a correctly versioned CLI Docker image and provide the Homebrew formula stub that the CI tap-update job expects.

**Architecture:** Two code changes in the repo (fix race condition in `Dockerfile.cli`, wire `--build-arg VERSION` in `release.yml`) plus one new file (Homebrew formula stub). The rest is a manual checklist for external service setup that only needs doing once.

**Tech Stack:** Docker BuildKit `ARG`, GitHub Actions, Homebrew Ruby formula, PyPI Trusted Publishers (OIDC), Docker Hub, npm.

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `Dockerfile.cli` | Modify | Add `ARG VERSION` + pin `pip install "agentbreeder==${VERSION}"` |
| `.github/workflows/release.yml` | Modify | Pass `--build-arg VERSION=...` to CLI image build step |
| `Formula/agentbreeder.rb` (new repo) | Create | Homebrew formula stub with regex-parseable URL/sha256 placeholders |

---

## Task 1: Fix Dockerfile.cli Version Race Condition

**Files:**
- Modify: `Dockerfile.cli`
- Modify: `.github/workflows/release.yml` (lines 160-173 — the CLI image build step)

The current `Dockerfile.cli` runs `pip install agentbreeder` with no version pin. The `build-images` CI job runs in parallel with `build-python`/`publish-pypi`. If the image build happens before PyPI publish completes, it installs the previous release. Fix: accept `VERSION` as a build arg and pin the install.

- [ ] **Step 1: Write the failing test**

The "test" here is inspection — run the release workflow locally with `act` and observe the race. We can codify it as a lint check instead:

```bash
# In Dockerfile.cli — confirm no unversioned pip install agentbreeder
grep 'pip install' Dockerfile.cli | grep -v 'agentbreeder==' && echo "FAIL: unversioned install" || echo "PASS"
```

Expected before fix: `FAIL: unversioned install`

- [ ] **Step 2: Update `Dockerfile.cli`**

```dockerfile
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/agentbreeder/agentbreeder"
LABEL org.opencontainers.image.description="AgentBreeder CLI for CI/CD pipelines"

ARG VERSION
RUN pip install --no-cache-dir "agentbreeder==${VERSION}"

ENTRYPOINT ["agentbreeder"]
CMD ["--help"]
```

- [ ] **Step 3: Update `release.yml` — pass `--build-arg VERSION` to CLI image build**

Locate the "Build and push CLI image" step (currently around line 160). It reads:

```yaml
      - name: Build and push CLI image
        uses: docker/build-push-action@v6
        with:
          file: ./Dockerfile.cli
          push: true
          platforms: linux/amd64,linux/arm64
          tags: |
            rajits/agentbreeder-cli:${{ steps.version.outputs.version }}
            rajits/agentbreeder-cli:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Replace with:

```yaml
      - name: Build and push CLI image
        uses: docker/build-push-action@v6
        with:
          file: ./Dockerfile.cli
          push: true
          platforms: linux/amd64,linux/arm64
          build-args: |
            VERSION=${{ steps.version.outputs.version }}
          tags: |
            rajits/agentbreeder-cli:${{ steps.version.outputs.version }}
            rajits/agentbreeder-cli:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

> **Note:** The `build-images` job still runs in parallel with `publish-pypi`. The version pin ensures the correct version is installed — but the CLI image build will fail if PyPI publish hasn't completed yet when the build runs. This is acceptable: the build-images job can be re-run, and the version pin is the correctness fix. If you want full ordering, add `needs: [pre-release-check, publish-pypi]` to the `build-images` job — but this serialises the pipeline and slows releases. The current parallel structure is fine for now.

- [ ] **Step 4: Verify the fix**

```bash
grep 'pip install' Dockerfile.cli | grep -v 'agentbreeder==' && echo "FAIL: unversioned install" || echo "PASS"
```

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.cli .github/workflows/release.yml
git commit -m "fix: pin agentbreeder version in Dockerfile.cli build arg

Pass VERSION as a Docker build arg so the CLI image always installs
the exact release version rather than whatever is latest on PyPI.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Create Homebrew Formula Stub

**Files:**
- Create: `Formula/agentbreeder.rb` (in the `agentbreeder/homebrew-agentbreeder` tap repo — **not** in this repo)

The `update-homebrew` CI job (`.github/workflows/release.yml`) checks out `agentbreeder/homebrew-agentbreeder` and runs regex replacements on `Formula/agentbreeder.rb`. If the file doesn't exist, the workflow fails. The stub just needs to have the right regex-parseable structure — it will be overwritten by CI on first release.

- [ ] **Step 1: Create the tap repo on GitHub**

Go to https://github.com/new and create a public repo named `homebrew-agentbreeder` under the `rajitsaha` account. Initialize it with a README.

- [ ] **Step 2: Clone the tap repo locally**

```bash
git clone git@github.com:agentbreeder/homebrew-agentbreeder.git /tmp/homebrew-agentbreeder
cd /tmp/homebrew-agentbreeder
mkdir -p Formula
```

- [ ] **Step 3: Write `Formula/agentbreeder.rb`**

```ruby
class Agentbreeder < Formula
  include Language::Python::Virtualenv

  desc "Define Once. Deploy Anywhere. — AgentBreeder CLI"
  homepage "https://github.com/agentbreeder/agentbreeder"
  url "https://files.pythonhosted.org/packages/placeholder/agentbreeder-0.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "Apache-2.0"

  depends_on "python@3.12"

  resource "agentbreeder-sdk" do
    url "https://files.pythonhosted.org/packages/placeholder/agentbreeder_sdk-0.0.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "AgentBreeder", shell_output("#{bin}/agentbreeder --help")
  end
end
```

> The `url`/`sha256` values use a specific regex pattern that the CI `update-homebrew` job matches. The `2-space indent + url` pattern is for the main package; `4-space indent + url` inside a `resource` block is for the SDK. Do not change this indentation — the CI regex depends on it exactly.

- [ ] **Step 4: Commit and push the formula**

```bash
cd /tmp/homebrew-agentbreeder
git add Formula/agentbreeder.rb
git commit -m "feat: add agentbreeder formula stub (updated by CI on each release)"
git push origin main
```

- [ ] **Step 5: Verify the tap works**

```bash
brew tap agentbreeder/agentbreeder
brew info agentbreeder/agentbreeder/agentbreeder
# Should print formula info — not an error about missing formula
```

---

## Task 3: Manual Setup Checklist

These steps require actions in external systems. They only need to be done once. None of them require code changes.

- [ ] **3a: Create PyPI projects + OIDC trusted publishers**

  1. Go to https://pypi.org and log in as `rajitsaha`
  2. If `agentbreeder` package doesn't exist yet: it will be created on first publish. Skip to step 3.
  3. For `agentbreeder`: Publishing → Trusted Publishers → Add publisher:
     - Owner: `rajitsaha`
     - Repository: `agentbreeder`
     - Workflow filename: `release.yml`
     - Environment name: `pypi`
  4. Repeat for `agentbreeder-sdk` with the same settings.
  5. Verify: both packages show the pending trusted publisher in their settings.

- [ ] **3b: Create GitHub Environment named `pypi`**

  1. Go to https://github.com/agentbreeder/agentbreeder → Settings → Environments → New environment
  2. Name it exactly `pypi` (case-sensitive — matches `release.yml`)
  3. No protection rules needed (PyPI OIDC handles the auth)
  4. Save.

- [ ] **3c: Create Docker Hub repos + set secrets**

  1. Go to https://hub.docker.com and log in as `rajits`
  2. Create three repos (public):
     - `rajits/agentbreeder-api`
     - `rajits/agentbreeder-dashboard`
     - `rajits/agentbreeder-cli`
  3. Go to Docker Hub → Account Settings → Security → Access Tokens → New Token
     - Description: `agentbreeder-ci`
     - Permissions: Read, Write, Delete
     - Copy the token
  4. Go to https://github.com/agentbreeder/agentbreeder → Settings → Secrets and variables → Actions
  5. Add secrets:
     - `DOCKERHUB_USERNAME` = `rajits`
     - `DOCKERHUB_TOKEN` = (the token from step 3)

- [ ] **3d: Create HOMEBREW_TAP_TOKEN secret**

  1. Go to https://github.com/settings/tokens/new?scopes=repo (GitHub → Settings → Developer Settings → Personal access tokens → Tokens classic)
  2. Name: `homebrew-tap-token`
  3. Expiration: No expiration (or 1 year — your call)
  4. Scopes: check `repo` only
  5. Generate and copy the token
  6. Go to https://github.com/agentbreeder/agentbreeder → Settings → Secrets → Actions
  7. Add secret: `HOMEBREW_TAP_TOKEN` = (the token from step 5)

- [ ] **3e: Create npm org + package + NPM_TOKEN secret**

  1. Go to https://www.npmjs.com and log in
  2. Create org `agentbreeder` (needed for `@agentbreeder/sdk` scoped package)
  3. Go to Access Tokens → Generate New Token → Automation (for CI)
  4. Copy the token
  5. Go to https://github.com/agentbreeder/agentbreeder → Settings → Secrets → Actions
  6. Add secret: `NPM_TOKEN` = (the token from step 4)

- [ ] **3f: Smoke-test the full release pipeline**

  Once all secrets are set and the Homebrew tap formula stub exists:

  ```bash
  # Tag a test release candidate from main
  git tag v0.1.0-rc1
  git push origin v0.1.0-rc1
  ```

  Watch https://github.com/agentbreeder/agentbreeder/actions — all jobs should go green:
  - `pre-release-check` → `build-python` / `build-sdk` / `build-images` / `build-ts-sdk`
  - `github-release` → `publish-sdk-pypi` → `publish-pypi` → `update-homebrew`
  - `publish-npm` (parallel with above)

  After green, verify:
  ```bash
  pip install agentbreeder==0.1.0rc1   # should install
  docker pull rajits/agentbreeder-cli:0.1.0rc1   # should pull
  brew tap agentbreeder/agentbreeder && brew install agentbreeder  # should install
  npm install @agentbreeder/sdk@0.1.0-rc1  # should install
  ```

---

## Self-Review

- **Spec coverage:** CLAUDE.md §Package Distribution Architecture describes PyPI (2 packages), Docker Hub (3 images), Homebrew tap. All covered. npm was added in the workflow but not in CLAUDE.md — that's existing state, not a gap in this plan.
- **No placeholders:** All steps have exact commands and URLs.
- **Type consistency:** No types involved — this is infra/config only.
- **Scope:** Minimal — one bug fix (Dockerfile.cli), one new file in a separate repo (formula stub), one manual checklist. No speculative additions.
