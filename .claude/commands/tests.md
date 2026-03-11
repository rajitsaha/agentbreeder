# /tests — Comprehensive Test Suite Generator

You are a test engineer. Your job is to create and run tests until they ALL pass and coverage reaches at least 95%.

## Rules

1. **Avoid mocks wherever possible.** Use real implementations, test databases, test servers, fixtures, and factory functions. Only mock external APIs or services that cannot be run locally.
2. **Fix failing tests** — do not skip, disable, or mark tests as xfail. Keep iterating until every test passes.
3. **Target 95%+ coverage** on changed/new files. Run coverage after each round and add tests for uncovered lines.
4. **Do NOT ask for permission** — just write tests, run them, fix failures, repeat.

## Test Types to Create

### 1. Unit Tests (`tests/unit/`)
- Test individual functions, classes, and methods in isolation
- Test edge cases: empty inputs, None values, invalid types, boundary conditions
- Test error paths: ensure proper exceptions are raised
- Use `pytest` fixtures and `tmp_path` for file operations
- Use `typer.testing.CliRunner` for CLI command tests

### 2. Integration Tests (`tests/integration/`)
- Test API routes end-to-end using `httpx.AsyncClient` with the real FastAPI app
- Test database operations with a real test database (SQLite in-memory or test PostgreSQL)
- Test CLI → API → DB round trips where applicable
- Test registry service classes with real database sessions

### 3. System / E2E Tests
- **Backend E2E** (`tests/e2e/`): Full workflow tests (create agent → deploy → verify registry)
- **Frontend E2E** (`dashboard/tests/e2e/`): Playwright tests for dashboard pages

## Execution Steps

1. **Analyze current coverage:**
   ```
   ./venv/bin/python -m pytest tests/unit/ --cov=. --cov-report=term-missing -q
   ```

2. **Identify gaps:** Find files/functions with < 95% coverage

3. **Write tests** for uncovered code — prioritize:
   - New/changed files first
   - Core engine code (config_parser, deployers, runtimes, resolver)
   - API routes and services
   - CLI commands
   - Registry services

4. **Run tests and fix failures:**
   ```
   ./venv/bin/python -m pytest tests/unit/ -v --tb=short
   ```

5. **Lint test files:**
   ```
   ./venv/bin/ruff check tests/
   ```

6. **Repeat** until all tests pass AND coverage >= 95%

## Test Patterns

### API Route Tests (use real FastAPI test client)
```python
from httpx import ASGITransport, AsyncClient
from api.main import app

async def test_list_agents():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 200
```

### CLI Tests (use CliRunner)
```python
from typer.testing import CliRunner
from cli.main import app
runner = CliRunner()

def test_command():
    result = runner.invoke(app, ["command", "arg"])
    assert result.exit_code == 0
```

### Database Tests (use real SQLite in-memory)
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
```

## Output

After completion, print a summary:
```
Tests: X passed, Y failed
Coverage: XX%
Files tested: [list]
```
