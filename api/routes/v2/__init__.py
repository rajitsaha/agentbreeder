"""API v2 routes — promoted endpoints from v1 plus new v2-only endpoints.

v2 is currently in preview. Endpoints here are stable once v2 is marked GA
in the release notes. Until then, they may change without notice.

v2 design goals vs v1:
- Cursor-based pagination (replaces offset/page pagination)
- Enveloped responses with richer metadata (request_id, version, timing)
- Consistent field naming: snake_case throughout, no legacy aliases
- Batch endpoints for bulk operations
- Streaming support on long-running endpoints (deploys, evals)
"""
