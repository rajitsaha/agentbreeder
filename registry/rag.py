"""RAG Backend Registry — factory that maps ``backend:`` keys to implementations.

This is the single source of truth for which backend handles which ``backend:``
value in ``rag.yaml``.  All callers go through ``get_rag_backend()``; they never
instantiate backend classes directly.

Supported backends
------------------
- ``in_memory``  — default, no external deps (``api.services.rag_service.RAGStore``)
- ``pgvector``   — PostgreSQL + pgvector (planned; currently aliased to in_memory)
- ``neo4j``      — Neo4j graph database (``api.services.neo4j_rag_backend``)

Adding a new backend
--------------------
1. Implement the class in ``api/services/``.
2. Add an entry to ``_BACKEND_REGISTRY`` mapping the ``backend:`` string key to a
   callable factory ``(config: dict, index_id: str) -> BackendInstance``.
3. Done — no other files need to change.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend type constants (mirrors rag.schema.json enum values)
# ---------------------------------------------------------------------------

BACKEND_IN_MEMORY = "in_memory"
BACKEND_PGVECTOR = "pgvector"
BACKEND_NEO4J = "neo4j"

_SUPPORTED_BACKENDS: frozenset[str] = frozenset(
    {BACKEND_IN_MEMORY, BACKEND_PGVECTOR, BACKEND_NEO4J}
)

# ---------------------------------------------------------------------------
# Internal factory registry
# ---------------------------------------------------------------------------


def _make_in_memory(config: dict[str, Any], index_id: str) -> Any:  # noqa: ANN401
    """Return a fresh RAGStore (in-memory singleton is managed by the store itself)."""
    from api.services.rag_service import get_rag_store  # noqa: PLC0415

    return get_rag_store()


def _make_pgvector(config: dict[str, Any], index_id: str) -> Any:  # noqa: ANN401
    """pgvector backend — falls back to in-memory until the pgvector adapter is shipped."""
    logger.warning(
        "pgvector backend is not yet fully implemented; falling back to in_memory "
        "(index_id=%s). This will be addressed in a future release.",
        index_id,
    )
    return _make_in_memory(config, index_id)


def _make_neo4j(config: dict[str, Any], index_id: str) -> Any:  # noqa: ANN401
    """Return a Neo4jRAGBackend configured from *config*."""
    from api.services.neo4j_rag_backend import create_neo4j_backend  # noqa: PLC0415

    return create_neo4j_backend(config=config, index_id=index_id)


# Map backend key → factory callable
_BACKEND_REGISTRY: dict[str, Any] = {
    BACKEND_IN_MEMORY: _make_in_memory,
    BACKEND_PGVECTOR: _make_pgvector,
    BACKEND_NEO4J: _make_neo4j,
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_rag_backend(
    backend: str,
    config: dict[str, Any] | None = None,
    index_id: str = "default",
) -> Any:  # noqa: ANN401
    """Resolve a ``backend:`` string from rag.yaml to a backend instance.

    Args:
        backend:  One of ``"in_memory"``, ``"pgvector"``, ``"neo4j"``.
        config:   Optional backend-specific config dict (e.g. ``uri``, ``password``).
        index_id: Logical index name used by backends that namespace storage.

    Returns:
        Backend instance.  The exact type depends on the selected backend.

    Raises:
        ValueError: If ``backend`` is not a known key in the registry.
    """
    if backend not in _BACKEND_REGISTRY:
        raise ValueError(
            f"Unknown RAG backend '{backend}'. "
            f"Supported backends: {sorted(_SUPPORTED_BACKENDS)}"
        )

    factory = _BACKEND_REGISTRY[backend]
    instance = factory(config or {}, index_id)
    logger.debug(
        "RAG backend '%s' resolved to %s (index_id=%s)",
        backend,
        type(instance).__name__,
        index_id,
    )
    return instance


def list_backends() -> list[str]:
    """Return all registered backend keys (sorted)."""
    return sorted(_BACKEND_REGISTRY.keys())
