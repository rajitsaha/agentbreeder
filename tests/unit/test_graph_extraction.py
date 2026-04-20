"""Unit tests for api.services.graph_extraction."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, patch

import pytest

from api.services.graph_extraction import (
    _normalize_entity_name,
    _parse_extraction_result,
    clear_extraction_cache,
    extract_entities,
    extract_entities_batch,
    get_extraction_cache,
)
from api.services.rag_service import DEFAULT_ENTITY_MODEL, GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_RESULT = {
    "entities": [
        {"entity": "Acme Corp", "type": "organization", "description": "A company"},
        {"entity": "Alice", "type": "person", "description": "An engineer"},
    ],
    "relationships": [
        {"subject": "Alice", "predicate": "works at", "object": "Acme Corp"},
    ],
}

EMPTY_RESULT: dict = {"entities": [], "relationships": []}


# ---------------------------------------------------------------------------
# _normalize_entity_name
# ---------------------------------------------------------------------------


def test_normalize_entity_name_lowercase():
    assert _normalize_entity_name("OpenAI") == "openai"


def test_normalize_entity_name_strip():
    assert _normalize_entity_name("  hello  ") == "hello"


def test_normalize_entity_name_collapse_whitespace():
    assert _normalize_entity_name("New  York   City") == "new york city"


def test_normalize_entity_name_combined():
    assert _normalize_entity_name("  Acme   Corp  ") == "acme corp"


# ---------------------------------------------------------------------------
# _parse_extraction_result — happy path
# ---------------------------------------------------------------------------


def test_parse_extraction_result_happy_path():
    nodes, edges = _parse_extraction_result(SIMPLE_RESULT, "some text")

    assert len(nodes) == 2
    entity_names = {n.entity for n in nodes}
    assert entity_names == {"Acme Corp", "Alice"}

    assert len(edges) == 1
    edge = edges[0]
    assert edge.predicate == "works at"
    # chunk_ids must be empty — caller must populate
    assert edge.chunk_ids == []
    for node in nodes:
        assert node.chunk_ids == []

    # Edge subject/object must resolve to real node ids
    node_ids = {n.id for n in nodes}
    assert edge.subject_id in node_ids
    assert edge.object_id in node_ids


# ---------------------------------------------------------------------------
# _parse_extraction_result — dangling edge
# ---------------------------------------------------------------------------


def test_parse_extraction_result_dangling_edge():
    data = {
        "entities": [
            {"entity": "Alice", "type": "person", "description": ""},
        ],
        "relationships": [
            # "Bob" is not in entities list
            {"subject": "Alice", "predicate": "knows", "object": "Bob"},
        ],
    }
    nodes, edges = _parse_extraction_result(data, "text")
    assert len(nodes) == 1
    assert len(edges) == 0


# ---------------------------------------------------------------------------
# _parse_extraction_result — malformed entity
# ---------------------------------------------------------------------------


def test_parse_extraction_result_malformed_entity():
    data = {
        "entities": [
            {"type": "person", "description": "missing entity key"},
            {"entity": "Valid", "type": "concept", "description": "ok"},
        ],
        "relationships": [],
    }
    nodes, edges = _parse_extraction_result(data, "text")
    # Only the valid entity survives
    assert len(nodes) == 1
    assert nodes[0].entity == "Valid"
    assert edges == []


# ---------------------------------------------------------------------------
# _parse_extraction_result — empty
# ---------------------------------------------------------------------------


def test_parse_extraction_result_empty():
    nodes, edges = _parse_extraction_result(EMPTY_RESULT, "text")
    assert nodes == []
    assert edges == []


# ---------------------------------------------------------------------------
# extract_entities — cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_cache_hit():
    """Cache hit must return stored value without calling _call_claude."""
    cache: dict = {}
    # Pre-populate cache with the exact key that extract_entities would compute
    cache_key = hashlib.sha256(
        json.dumps({"text": "hello", "model": DEFAULT_ENTITY_MODEL}, sort_keys=True).encode()
    ).hexdigest()
    cached_nodes = [GraphNode(id="n1", entity="Cached", entity_type="concept", description="", chunk_ids=[])]
    cached_edges: list[GraphEdge] = []
    cache[cache_key] = (cached_nodes, cached_edges)

    with patch("api.services.graph_extraction._call_claude", new_callable=AsyncMock) as mock_call:
        nodes, edges = await extract_entities("hello", cache=cache)

    mock_call.assert_not_called()
    assert nodes is cached_nodes
    assert edges is cached_edges


# ---------------------------------------------------------------------------
# extract_entities — cache miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_cache_miss():
    """Cache miss must call _call_claude and store the result."""
    cache: dict = {}

    with patch(
        "api.services.graph_extraction._call_claude",
        new_callable=AsyncMock,
        return_value=SIMPLE_RESULT,
    ) as mock_call:
        nodes, edges = await extract_entities("some text", cache=cache)

    mock_call.assert_called_once()
    assert len(nodes) == 2
    assert len(edges) == 1
    # Result must be stored in the cache
    assert len(cache) == 1


# ---------------------------------------------------------------------------
# extract_entities — missing API key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_api_key_missing(monkeypatch):
    """When ANTHROPIC_API_KEY is absent, extract_entities returns ([], [])."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cache: dict = {}

    nodes, edges = await extract_entities("text without key", cache=cache)

    assert nodes == []
    assert edges == []


# ---------------------------------------------------------------------------
# extract_entities_batch — ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_batch_ordering():
    """Results must be returned in the same order as input texts."""
    texts = ["chunk_a", "chunk_b", "chunk_c"]

    call_count = 0

    async def fake_call_claude(text: str, model: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {
            "entities": [{"entity": text, "type": "concept", "description": ""}],
            "relationships": [],
        }

    with patch("api.services.graph_extraction._call_claude", side_effect=fake_call_claude):
        results = await extract_entities_batch(texts, cache={})

    assert len(results) == 3
    for i, text in enumerate(texts):
        nodes, edges = results[i]
        assert len(nodes) == 1
        assert nodes[0].entity == text


# ---------------------------------------------------------------------------
# Cache key collision safety
# ---------------------------------------------------------------------------


def test_cache_key_collision_safe():
    """Two (text, model) pairs that differ only by pipe chars yield different keys."""
    # With naive f"{text}|{model}" these would collide:
    #   text="a|b", model="c"  →  "a|b|c"
    #   text="a",   model="b|c" → "a|b|c"
    key1 = hashlib.sha256(
        json.dumps({"text": "a|b", "model": "c"}, sort_keys=True).encode()
    ).hexdigest()
    key2 = hashlib.sha256(
        json.dumps({"text": "a", "model": "b|c"}, sort_keys=True).encode()
    ).hexdigest()
    assert key1 != key2


# ---------------------------------------------------------------------------
# clear_extraction_cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_extraction_cache():
    """After clear, module-level cache is empty."""
    # Populate the module-level cache via extract_entities
    with patch(
        "api.services.graph_extraction._call_claude",
        new_callable=AsyncMock,
        return_value=SIMPLE_RESULT,
    ):
        await extract_entities("populate the cache")

    # Verify it has an entry
    assert len(get_extraction_cache()) >= 1

    clear_extraction_cache()

    assert len(get_extraction_cache()) == 0
