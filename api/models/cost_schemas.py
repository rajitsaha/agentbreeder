"""Pydantic schemas for cost tracking and budget management."""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Cost Event Schemas ---


class CostEventCreate(BaseModel):
    """Request body to record a cost event."""

    trace_id: str | None = None
    agent_id: str | None = None
    agent_name: str
    team: str
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_type: str = "chat"  # "chat", "embedding", "tool_call"


class CostEventResponse(BaseModel):
    """A single cost event."""

    id: str
    trace_id: str | None = None
    agent_id: str | None = None
    agent_name: str
    team: str
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    request_type: str
    created_at: str


# --- Summary & Breakdown ---


class CostSummary(BaseModel):
    """Aggregated cost summary over a period."""

    total_cost: float
    total_tokens: int
    request_count: int
    period: str  # e.g. "30d"


class CostBreakdownItem(BaseModel):
    """A single item in a cost breakdown."""

    name: str
    cost: float
    tokens: int = 0
    requests: int = 0


class CostBreakdown(BaseModel):
    """Cost breakdown by agent, model, or team."""

    by_agent: list[CostBreakdownItem] = Field(default_factory=list)
    by_model: list[CostBreakdownItem] = Field(default_factory=list)
    by_team: list[CostBreakdownItem] = Field(default_factory=list)


# --- Trend ---


class DailyCostPoint(BaseModel):
    """A single day's cost data."""

    date: str
    cost: float
    tokens: int
    requests: int


class CostTrendResponse(BaseModel):
    """Daily cost trend over a period."""

    points: list[DailyCostPoint] = Field(default_factory=list)
    total_cost: float = 0.0
    period: str = "30d"


# --- Budget Schemas ---


class BudgetCreate(BaseModel):
    """Request body to create or set a team budget."""

    team: str
    monthly_limit_usd: float
    alert_threshold_pct: float = 80.0


class BudgetUpdate(BaseModel):
    """Request body to update a team budget."""

    monthly_limit_usd: float | None = None
    alert_threshold_pct: float | None = None


class BudgetResponse(BaseModel):
    """A team's budget status."""

    id: str
    team: str
    monthly_limit_usd: float
    alert_threshold_pct: float
    current_month_spend: float
    pct_used: float
    is_exceeded: bool
    created_at: str
    updated_at: str


# --- Model Comparison ---


class CostComparisonRequest(BaseModel):
    """Request to compare costs between two models."""

    model_a: str
    model_b: str
    sample_tokens: int = 1_000_000


class CostComparisonResponse(BaseModel):
    """Result of a model cost comparison."""

    model_a: str
    model_b: str
    model_a_cost: float
    model_b_cost: float
    savings_pct: float
    sample_tokens: int
