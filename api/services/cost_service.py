"""Cost Tracking Service — in-memory store for cost events and budgets.

Provides:
- Cost event recording and querying
- Cost summaries, breakdowns, and trends
- Team budget management and checking
- Model cost comparison
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model Pricing (per million tokens)
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4.5": {"input": 0.80, "output": 4.00},
    "claude-opus-4.6": {"input": 15.00, "output": 75.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


class CostEventRecord:
    """In-memory cost event record."""

    def __init__(
        self,
        *,
        event_id: str,
        trace_id: str | None,
        agent_id: str | None,
        agent_name: str,
        team: str,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        request_type: str,
        created_at: str,
    ) -> None:
        self.id = event_id
        self.trace_id = trace_id
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.team = team
        self.model_name = model_name
        self.provider = provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.cost_usd = cost_usd
        self.request_type = request_type
        self.created_at = created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "team": self.team,
            "model_name": self.model_name,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "request_type": self.request_type,
            "created_at": self.created_at,
        }


class BudgetRecord:
    """In-memory budget record."""

    def __init__(
        self,
        *,
        budget_id: str,
        team: str,
        monthly_limit_usd: float,
        alert_threshold_pct: float = 80.0,
        current_month_spend: float = 0.0,
        is_exceeded: bool = False,
        created_at: str,
        updated_at: str,
    ) -> None:
        self.id = budget_id
        self.team = team
        self.monthly_limit_usd = monthly_limit_usd
        self.alert_threshold_pct = alert_threshold_pct
        self.current_month_spend = current_month_spend
        self.is_exceeded = is_exceeded
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def pct_used(self) -> float:
        if self.monthly_limit_usd <= 0:
            return 0.0
        return round(self.current_month_spend / self.monthly_limit_usd * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "team": self.team,
            "monthly_limit_usd": self.monthly_limit_usd,
            "alert_threshold_pct": self.alert_threshold_pct,
            "current_month_spend": round(self.current_month_spend, 6),
            "pct_used": self.pct_used,
            "is_exceeded": self.is_exceeded,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# In-Memory Store
# ---------------------------------------------------------------------------


class CostStore:
    """In-memory store for cost events and budgets.

    Will be replaced by PostgreSQL when the real DB is connected.
    """

    def __init__(self) -> None:
        self._events: dict[str, CostEventRecord] = {}
        self._budgets: dict[str, BudgetRecord] = {}  # keyed by team

    # --- Cost Events ---

    def record_cost_event(
        self,
        *,
        trace_id: str | None = None,
        agent_id: str | None = None,
        agent_name: str,
        team: str,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        request_type: str = "chat",
    ) -> CostEventRecord:
        """Record a new cost event and update the team budget spend."""
        event_id = str(uuid.uuid4())
        total_tokens = input_tokens + output_tokens
        now = datetime.now(UTC).isoformat()

        event = CostEventRecord(
            event_id=event_id,
            trace_id=trace_id,
            agent_id=agent_id,
            agent_name=agent_name,
            team=team,
            model_name=model_name,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            request_type=request_type,
            created_at=now,
        )
        self._events[event_id] = event

        # Update budget spend
        if team in self._budgets:
            budget = self._budgets[team]
            budget.current_month_spend += cost_usd
            budget.is_exceeded = budget.current_month_spend >= budget.monthly_limit_usd
            budget.updated_at = now

        logger.info(
            "Cost event recorded",
            extra={"agent": agent_name, "team": team, "cost": cost_usd},
        )
        return event

    def _filter_events(
        self,
        *,
        team: str | None = None,
        agent_name: str | None = None,
        days: int = 30,
    ) -> list[CostEventRecord]:
        """Filter events by team, agent name, and time window."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        results: list[CostEventRecord] = []
        for event in self._events.values():
            if event.created_at < cutoff:
                continue
            if team and event.team != team:
                continue
            if agent_name and event.agent_name != agent_name:
                continue
            results.append(event)
        return results

    def get_cost_summary(
        self,
        *,
        team: str | None = None,
        agent_name: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get aggregated cost summary."""
        events = self._filter_events(team=team, agent_name=agent_name, days=days)
        total_cost = sum(e.cost_usd for e in events)
        total_tokens = sum(e.total_tokens for e in events)
        return {
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "request_count": len(events),
            "period": f"{days}d",
        }

    def get_cost_breakdown(
        self,
        *,
        days: int = 30,
        group_by: str = "agent",
    ) -> dict[str, Any]:
        """Get cost breakdown grouped by agent, model, or team."""
        events = self._filter_events(days=days)

        by_agent: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"cost": 0.0, "tokens": 0, "requests": 0}
        )
        by_model: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"cost": 0.0, "tokens": 0, "requests": 0}
        )
        by_team: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"cost": 0.0, "tokens": 0, "requests": 0}
        )

        for e in events:
            by_agent[e.agent_name]["cost"] += e.cost_usd
            by_agent[e.agent_name]["tokens"] += e.total_tokens
            by_agent[e.agent_name]["requests"] += 1

            by_model[e.model_name]["cost"] += e.cost_usd
            by_model[e.model_name]["tokens"] += e.total_tokens
            by_model[e.model_name]["requests"] += 1

            by_team[e.team]["cost"] += e.cost_usd
            by_team[e.team]["tokens"] += e.total_tokens
            by_team[e.team]["requests"] += 1

        def _to_list(d: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            items = [
                {
                    "name": name,
                    "cost": round(data["cost"], 6),
                    "tokens": data["tokens"],
                    "requests": data["requests"],
                }
                for name, data in d.items()
            ]
            items.sort(key=lambda x: x["cost"], reverse=True)
            return items

        return {
            "by_agent": _to_list(by_agent),
            "by_model": _to_list(by_model),
            "by_team": _to_list(by_team),
        }

    def get_cost_trend(
        self,
        *,
        days: int = 30,
        team: str | None = None,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        """Get daily cost trend data."""
        events = self._filter_events(team=team, agent_name=agent_name, days=days)

        daily: dict[str, dict[str, Any]] = {}
        for i in range(days):
            date_str = (datetime.now(UTC) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            daily[date_str] = {"cost": 0.0, "tokens": 0, "requests": 0}

        for e in events:
            date_str = e.created_at[:10]  # YYYY-MM-DD
            if date_str in daily:
                daily[date_str]["cost"] += e.cost_usd
                daily[date_str]["tokens"] += e.total_tokens
                daily[date_str]["requests"] += 1

        points = [
            {
                "date": date,
                "cost": round(data["cost"], 6),
                "tokens": data["tokens"],
                "requests": data["requests"],
            }
            for date, data in sorted(daily.items())
        ]
        total_cost = sum(p["cost"] for p in points)

        return {
            "points": points,
            "total_cost": round(total_cost, 6),
            "period": f"{days}d",
        }

    def get_top_spenders(
        self,
        *,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get top N agents by cost."""
        events = self._filter_events(days=days)
        agent_costs: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"cost": 0.0, "tokens": 0, "requests": 0, "team": ""}
        )
        for e in events:
            agent_costs[e.agent_name]["cost"] += e.cost_usd
            agent_costs[e.agent_name]["tokens"] += e.total_tokens
            agent_costs[e.agent_name]["requests"] += 1
            agent_costs[e.agent_name]["team"] = e.team

        items = [
            {
                "agent_name": name,
                "cost": round(data["cost"], 6),
                "tokens": data["tokens"],
                "requests": data["requests"],
                "team": data["team"],
            }
            for name, data in agent_costs.items()
        ]
        items.sort(key=lambda x: x["cost"], reverse=True)
        return items[:limit]

    # --- Budgets ---

    def create_budget(
        self,
        *,
        team: str,
        monthly_limit_usd: float,
        alert_threshold_pct: float = 80.0,
    ) -> BudgetRecord:
        """Create or replace a team budget."""
        now = datetime.now(UTC).isoformat()
        budget_id = str(uuid.uuid4())

        # Preserve current spend if budget already exists
        existing = self._budgets.get(team)
        current_spend = existing.current_month_spend if existing else 0.0

        budget = BudgetRecord(
            budget_id=budget_id,
            team=team,
            monthly_limit_usd=monthly_limit_usd,
            alert_threshold_pct=alert_threshold_pct,
            current_month_spend=current_spend,
            is_exceeded=current_spend >= monthly_limit_usd,
            created_at=now,
            updated_at=now,
        )
        self._budgets[team] = budget
        logger.info("Budget created", extra={"team": team, "limit": monthly_limit_usd})
        return budget

    def get_budget(self, team: str) -> BudgetRecord | None:
        """Get a team's budget."""
        return self._budgets.get(team)

    def list_budgets(self) -> list[BudgetRecord]:
        """List all budgets."""
        return sorted(self._budgets.values(), key=lambda b: b.team)

    def update_budget(
        self,
        team: str,
        *,
        monthly_limit_usd: float | None = None,
        alert_threshold_pct: float | None = None,
    ) -> BudgetRecord | None:
        """Update a team's budget settings."""
        budget = self._budgets.get(team)
        if not budget:
            return None
        if monthly_limit_usd is not None:
            budget.monthly_limit_usd = monthly_limit_usd
            budget.is_exceeded = budget.current_month_spend >= monthly_limit_usd
        if alert_threshold_pct is not None:
            budget.alert_threshold_pct = alert_threshold_pct
        budget.updated_at = datetime.now(UTC).isoformat()
        return budget

    def check_budget(self, team: str) -> dict[str, Any]:
        """Check whether a team is within budget."""
        budget = self._budgets.get(team)
        if not budget:
            return {"within_budget": True, "pct_used": 0.0, "has_budget": False}
        return {
            "within_budget": not budget.is_exceeded,
            "pct_used": budget.pct_used,
            "has_budget": True,
        }

    # --- Model Comparison ---

    def compare_models(
        self,
        model_a: str,
        model_b: str,
        sample_tokens: int = 1_000_000,
    ) -> dict[str, Any]:
        """Compare estimated costs for two models."""
        pricing_a = MODEL_PRICING.get(model_a, {"input": 0.0, "output": 0.0})
        pricing_b = MODEL_PRICING.get(model_b, {"input": 0.0, "output": 0.0})

        # Assume 50/50 split between input and output for the sample
        half = sample_tokens / 2
        cost_a = (half * pricing_a["input"] + half * pricing_a["output"]) / 1_000_000
        cost_b = (half * pricing_b["input"] + half * pricing_b["output"]) / 1_000_000

        savings_pct = 0.0
        if cost_a > 0:
            savings_pct = round((1 - cost_b / cost_a) * 100, 2)

        return {
            "model_a": model_a,
            "model_b": model_b,
            "model_a_cost": round(cost_a, 6),
            "model_b_cost": round(cost_b, 6),
            "savings_pct": savings_pct,
            "sample_tokens": sample_tokens,
        }


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

_store: CostStore | None = None


def get_cost_store() -> CostStore:
    """Get the global cost store singleton."""
    global _store
    if _store is None:
        _store = CostStore()
    return _store
