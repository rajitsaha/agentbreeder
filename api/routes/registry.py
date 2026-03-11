"""Registry API routes — tools, models, prompts, knowledge bases."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.schemas import (
    ApiMeta,
    ApiResponse,
    ModelCreate,
    ModelResponse,
    PromptCreate,
    PromptResponse,
    PromptUpdate,
    ToolCreate,
    ToolResponse,
    SearchResult,
)
from registry.agents import AgentRegistry
from registry.models import ModelRegistry
from registry.prompts import PromptRegistry
from registry.tools import ToolRegistry

router = APIRouter(prefix="/api/v1/registry", tags=["registry"])


@router.get("/tools", response_model=ApiResponse[list[ToolResponse]])
async def list_tools(
    tool_type: str | None = Query(None),
    source: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ToolResponse]]:
    """List tools and MCP servers from the registry."""
    tools, total = await ToolRegistry.list(
        db, tool_type=tool_type, source=source, page=page, per_page=per_page
    )
    return ApiResponse(
        data=[ToolResponse.model_validate(t) for t in tools],
        meta=ApiMeta(page=page, per_page=per_page, total=total),
    )


@router.post("/tools", response_model=ApiResponse[ToolResponse], status_code=201)
async def register_tool(
    body: ToolCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ToolResponse]:
    """Register a tool or MCP server."""
    tool = await ToolRegistry.register(
        db,
        name=body.name,
        description=body.description,
        tool_type=body.tool_type,
        schema_definition=body.schema_definition,
        endpoint=body.endpoint,
        source=body.source,
    )
    return ApiResponse(data=ToolResponse.model_validate(tool))


@router.get("/models", response_model=ApiResponse[list[ModelResponse]])
async def list_models(
    provider: str | None = Query(None),
    source: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ModelResponse]]:
    """List LLM models from the registry."""
    models, total = await ModelRegistry.list(
        db, provider=provider, source=source, page=page, per_page=per_page
    )
    return ApiResponse(
        data=[ModelResponse.model_validate(m) for m in models],
        meta=ApiMeta(page=page, per_page=per_page, total=total),
    )


@router.post("/models", response_model=ApiResponse[ModelResponse], status_code=201)
async def register_model(
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ModelResponse]:
    """Register an LLM model."""
    model = await ModelRegistry.register(
        db,
        name=body.name,
        provider=body.provider,
        description=body.description,
        config=body.config,
        source=body.source,
    )
    return ApiResponse(data=ModelResponse.model_validate(model))


@router.get("/prompts", response_model=ApiResponse[list[PromptResponse]])
async def list_prompts(
    team: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[PromptResponse]]:
    """List prompt templates from the registry."""
    prompts, total = await PromptRegistry.list(
        db, team=team, page=page, per_page=per_page
    )
    return ApiResponse(
        data=[PromptResponse.model_validate(p) for p in prompts],
        meta=ApiMeta(page=page, per_page=per_page, total=total),
    )


@router.post("/prompts", response_model=ApiResponse[PromptResponse], status_code=201)
async def register_prompt(
    body: PromptCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    """Register a prompt template."""
    prompt = await PromptRegistry.register(
        db,
        name=body.name,
        version=body.version,
        content=body.content,
        description=body.description,
        team=body.team,
    )
    return ApiResponse(data=PromptResponse.model_validate(prompt))


@router.get("/prompts/{prompt_id}", response_model=ApiResponse[PromptResponse])
async def get_prompt(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    """Get a single prompt by ID."""
    prompt = await PromptRegistry.get_by_id(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data=PromptResponse.model_validate(prompt))


@router.put("/prompts/{prompt_id}", response_model=ApiResponse[PromptResponse])
async def update_prompt(
    prompt_id: str,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    """Update a prompt's content or description."""
    prompt = await PromptRegistry.update(
        db, prompt_id, content=body.content, description=body.description
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data=PromptResponse.model_validate(prompt))


@router.delete("/prompts/{prompt_id}", response_model=ApiResponse[dict])
async def delete_prompt(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    """Delete a prompt."""
    deleted = await PromptRegistry.delete(db, prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data={"deleted": True})


@router.get(
    "/prompts/{prompt_id}/versions",
    response_model=ApiResponse[list[PromptResponse]],
)
async def list_prompt_versions(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[PromptResponse]]:
    """List all versions of a prompt by name (looked up via the given id)."""
    versions = await PromptRegistry.get_versions(db, prompt_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(
        data=[PromptResponse.model_validate(p) for p in versions],
        meta=ApiMeta(page=1, per_page=len(versions), total=len(versions)),
    )


@router.post(
    "/prompts/{prompt_id}/duplicate",
    response_model=ApiResponse[PromptResponse],
    status_code=201,
)
async def duplicate_prompt(
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[PromptResponse]:
    """Duplicate a prompt as a new version."""
    prompt = await PromptRegistry.duplicate(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return ApiResponse(data=PromptResponse.model_validate(prompt))


@router.get("/search", response_model=ApiResponse[list[SearchResult]])
async def search_registry(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[SearchResult]]:
    """Search across all registry entities (agents, tools)."""
    results: list[SearchResult] = []

    # Search agents
    agents, _ = await AgentRegistry.search(db, query=q, page=1, per_page=per_page)
    for agent in agents:
        results.append(
            SearchResult(
                entity_type="agent",
                id=agent.id,
                name=agent.name,
                description=agent.description,
                team=agent.team,
            )
        )

    # Search tools
    tools, _ = await ToolRegistry.search(db, query=q, page=1, per_page=per_page)
    for tool in tools:
        results.append(
            SearchResult(
                entity_type="tool",
                id=tool.id,
                name=tool.name,
                description=tool.description,
            )
        )

    # Search models
    models, _ = await ModelRegistry.search(db, query=q, page=1, per_page=per_page)
    for model in models:
        results.append(
            SearchResult(
                entity_type="model",
                id=model.id,
                name=model.name,
                description=model.description,
            )
        )

    # Search prompts
    prompts, _ = await PromptRegistry.search(db, query=q, page=1, per_page=per_page)
    for prompt in prompts:
        results.append(
            SearchResult(
                entity_type="prompt",
                id=prompt.id,
                name=prompt.name,
                description=prompt.description,
                team=prompt.team,
            )
        )

    return ApiResponse(
        data=results[:per_page],
        meta=ApiMeta(page=page, per_page=per_page, total=len(results)),
    )
