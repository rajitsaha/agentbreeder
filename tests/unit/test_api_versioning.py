"""Tests for API versioning middleware and deprecation policy utilities."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.versioning import (
    DEPRECATED_PATHS,
    APIVersionMiddleware,
    _extract_version,
    deprecate_path,
)

# ── _extract_version ────────────────────────────────────────────────────────


def test_extract_version_v1():
    assert _extract_version("/api/v1/agents") == "v1"


def test_extract_version_v2():
    assert _extract_version("/api/v2/agents") == "v2"


def test_extract_version_no_version():
    assert _extract_version("/health") is None


def test_extract_version_non_api_path():
    assert _extract_version("/docs") is None


def test_extract_version_nested():
    assert _extract_version("/api/v1/agents/abc-123/tools") == "v1"


# ── deprecate_path ──────────────────────────────────────────────────────────


def test_deprecate_path_registers_entry():
    prefix = "/api/v1/_test_deprecation"
    deprecate_path(prefix, sunset="2099-01-01", successor="/api/v2/_test")
    assert prefix in DEPRECATED_PATHS
    assert DEPRECATED_PATHS[prefix]["sunset"] == "2099-01-01"
    assert DEPRECATED_PATHS[prefix]["successor"] == "/api/v2/_test"
    # Cleanup so we don't pollute other tests
    del DEPRECATED_PATHS[prefix]


def test_deprecate_path_no_successor():
    prefix = "/api/v1/_test_no_successor"
    deprecate_path(prefix, sunset="2099-01-01")
    assert DEPRECATED_PATHS[prefix]["successor"] == ""
    del DEPRECATED_PATHS[prefix]


# ── APIVersionMiddleware integration ────────────────────────────────────────


def _make_app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(APIVersionMiddleware)

    @app.get("/api/v1/ping")
    async def ping_v1():
        return {"pong": True}

    @app.get("/api/v2/ping")
    async def ping_v2():
        return {"pong": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app_with_middleware())


def test_middleware_adds_version_header_v1(client):
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.headers["X-API-Version"] == "v1"
    assert resp.headers["X-API-Latest"] == "v1"


def test_middleware_adds_version_header_v2(client):
    resp = client.get("/api/v2/ping")
    assert resp.status_code == 200
    assert resp.headers["X-API-Version"] == "v2"


def test_middleware_no_version_header_on_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-API-Version" not in resp.headers
    assert resp.headers["X-API-Latest"] == "v1"


def test_middleware_deprecation_headers(client):
    # Register a test path as deprecated
    deprecate_path("/api/v1/ping", sunset="2099-06-01", successor="/api/v2/ping")
    try:
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == 'date="2099-06-01"'
        assert resp.headers.get("Sunset") == "2099-06-01"
        link = resp.headers.get("Link", "")
        assert "/api/v2/ping" in link
        assert 'rel="successor-version"' in link
    finally:
        del DEPRECATED_PATHS["/api/v1/ping"]


def test_middleware_no_deprecation_on_clean_path(client):
    resp = client.get("/api/v1/ping")
    assert "Deprecation" not in resp.headers
    assert "Sunset" not in resp.headers
    assert "Link" not in resp.headers
