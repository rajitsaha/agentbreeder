# /launch — Pre-flight Check, Test, Secure, Commit & Push

You are a release engineer. Run all checks, fix issues, and push clean code to main.

## Do NOT ask for permission — just execute each step. Stop only if something is unfixable.

## Pipeline (execute in order)

### Step 1: Run /tests skill
Run the full test suite as defined in the `/tests` skill:
- Run all unit, integration, and E2E tests
- Fix any failing tests
- Ensure coverage >= 95% on changed files
- All tests must pass before proceeding

### Step 2: Lint & Format
```bash
./venv/bin/ruff check . --fix
./venv/bin/ruff format .
```
- Fix any remaining lint errors that `--fix` can't handle
- Ensure zero lint errors before proceeding

### Step 3: Vulnerability Check
```bash
# Python dependency vulnerabilities
./venv/bin/pip-audit 2>/dev/null || ./venv/bin/pip install pip-audit && ./venv/bin/pip-audit

# Check for secrets accidentally committed
grep -rn "sk-proj-\|sk-ant-\|AKIA\|ghp_\|gho_" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.yml" --include="*.json" . | grep -v node_modules | grep -v .env | grep -v venv | grep -v __pycache__ | grep -v ".claude/" || true
```

**For vulnerabilities found:**
- **Critical / High:** MUST fix before proceeding (upgrade dependency, patch, or mitigate)
- **Medium:** Fix if straightforward (< 5 min), otherwise note in commit message
- **Low:** Note but don't block

**For secrets found:**
- Remove immediately and add to `.gitignore` if needed
- NEVER commit real API keys, tokens, or credentials

### Step 4: Type Check (if applicable)
```bash
# Python
./venv/bin/mypy . --ignore-missing-imports 2>/dev/null || true

# TypeScript (dashboard)
cd dashboard && npm run typecheck 2>/dev/null || true
```
- Fix critical type errors. Warnings are OK.

### Step 5: Commit & Push
```bash
# Stage all changes
git add -A

# Check what's being committed (safety check)
git status
git diff --cached --stat

# Commit with descriptive message
git commit -m "<descriptive message>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# Push to main
git push origin main
```

**Commit message rules:**
- Summarize ALL changes (not just the last file)
- Use conventional format: `feat:`, `fix:`, `test:`, `chore:`
- Keep first line under 72 chars
- Add details in body if multiple changes

### Step 6: Post-push verification
```bash
git log --oneline -3
git status
```

## Output Summary

Print at the end:
```
=== Launch Summary ===
Tests:       X passed, 0 failed
Coverage:    XX%
Lint:        Clean
Vulnerabilities: X fixed, Y noted
Commit:      <hash> <message>
Pushed:      main → origin/main
```
