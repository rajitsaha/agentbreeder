"""Unit tests for the cost tracking service."""

from __future__ import annotations

import pytest

from api.services.cost_service import CostStore


@pytest.fixture
def store() -> CostStore:
    """Return a fresh CostStore for each test."""
    return CostStore()


def _record(store: CostStore, **kwargs) -> dict:
    """Helper to record a cost event with sensible defaults."""
    defaults = {
        "agent_name": "test-agent",
        "team": "engineering",
        "model_name": "gpt-4o",
        "provider": "openai",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.0075,
        "request_type": "chat",
    }
    defaults.update(kwargs)
    return store.record_cost_event(**defaults).to_dict()


# ---------------------------------------------------------------------------
# Cost Event Tests
# ---------------------------------------------------------------------------


class TestRecordCostEvent:
    def test_record_cost_event(self, store: CostStore) -> None:
        event = _record(store)
        assert event["agent_name"] == "test-agent"
        assert event["team"] == "engineering"
        assert event["model_name"] == "gpt-4o"
        assert event["input_tokens"] == 1000
        assert event["output_tokens"] == 500
        assert event["total_tokens"] == 1500
        assert event["cost_usd"] == 0.0075
        assert event["request_type"] == "chat"
        assert event["id"] is not None
        assert event["created_at"] is not None

    def test_record_multiple_events(self, store: CostStore) -> None:
        e1 = _record(store, agent_name="agent-a")
        e2 = _record(store, agent_name="agent-b")
        assert e1["id"] != e2["id"]


# ---------------------------------------------------------------------------
# Cost Summary Tests
# ---------------------------------------------------------------------------


class TestGetCostSummary:
    def test_get_cost_summary(self, store: CostStore) -> None:
        _record(store, cost_usd=1.0, input_tokens=1000, output_tokens=500)
        _record(store, cost_usd=2.0, input_tokens=2000, output_tokens=1000)

        summary = store.get_cost_summary()
        assert summary["total_cost"] == 3.0
        assert summary["total_tokens"] == 4500
        assert summary["request_count"] == 2
        assert summary["period"] == "30d"

    def test_summary_filter_by_team(self, store: CostStore) -> None:
        _record(store, team="eng", cost_usd=1.0)
        _record(store, team="sales", cost_usd=2.0)

        summary = store.get_cost_summary(team="eng")
        assert summary["total_cost"] == 1.0
        assert summary["request_count"] == 1

    def test_summary_filter_by_agent(self, store: CostStore) -> None:
        _record(store, agent_name="a1", cost_usd=1.0)
        _record(store, agent_name="a2", cost_usd=3.0)

        summary = store.get_cost_summary(agent_name="a1")
        assert summary["total_cost"] == 1.0

    def test_summary_empty_store(self, store: CostStore) -> None:
        summary = store.get_cost_summary()
        assert summary["total_cost"] == 0.0
        assert summary["total_tokens"] == 0
        assert summary["request_count"] == 0


# ---------------------------------------------------------------------------
# Cost Breakdown Tests
# ---------------------------------------------------------------------------


class TestGetCostBreakdown:
    def test_get_cost_breakdown_by_agent(self, store: CostStore) -> None:
        _record(store, agent_name="agent-a", cost_usd=3.0)
        _record(store, agent_name="agent-a", cost_usd=2.0)
        _record(store, agent_name="agent-b", cost_usd=1.0)

        breakdown = store.get_cost_breakdown()
        by_agent = breakdown["by_agent"]
        assert len(by_agent) == 2
        # Sorted by cost descending
        assert by_agent[0]["name"] == "agent-a"
        assert by_agent[0]["cost"] == 5.0
        assert by_agent[0]["requests"] == 2
        assert by_agent[1]["name"] == "agent-b"
        assert by_agent[1]["cost"] == 1.0

    def test_get_cost_breakdown_by_model(self, store: CostStore) -> None:
        _record(store, model_name="gpt-4o", cost_usd=2.0)
        _record(store, model_name="claude-sonnet-4.6", cost_usd=5.0)

        breakdown = store.get_cost_breakdown()
        by_model = breakdown["by_model"]
        assert len(by_model) == 2
        assert by_model[0]["name"] == "claude-sonnet-4.6"
        assert by_model[0]["cost"] == 5.0


# ---------------------------------------------------------------------------
# Cost Trend Tests
# ---------------------------------------------------------------------------


class TestGetCostTrend:
    def test_get_cost_trend(self, store: CostStore) -> None:
        _record(store, cost_usd=1.5)
        _record(store, cost_usd=2.5)

        trend = store.get_cost_trend(days=30)
        assert trend["period"] == "30d"
        assert len(trend["points"]) == 30
        assert trend["total_cost"] == 4.0

        # All events are today, so only today should have cost
        nonzero = [p for p in trend["points"] if p["cost"] > 0]
        assert len(nonzero) == 1
        assert nonzero[0]["cost"] == 4.0


# ---------------------------------------------------------------------------
# Budget Tests
# ---------------------------------------------------------------------------


class TestBudgets:
    def test_create_budget(self, store: CostStore) -> None:
        budget = store.create_budget(team="eng", monthly_limit_usd=100.0)
        assert budget.team == "eng"
        assert budget.monthly_limit_usd == 100.0
        assert budget.alert_threshold_pct == 80.0
        assert budget.current_month_spend == 0.0
        assert budget.is_exceeded is False

    def test_check_budget_within_limit(self, store: CostStore) -> None:
        store.create_budget(team="eng", monthly_limit_usd=100.0)
        _record(store, team="eng", cost_usd=50.0)

        result = store.check_budget("eng")
        assert result["within_budget"] is True
        assert result["pct_used"] == 50.0
        assert result["has_budget"] is True

    def test_check_budget_exceeded(self, store: CostStore) -> None:
        store.create_budget(team="eng", monthly_limit_usd=10.0)
        _record(store, team="eng", cost_usd=15.0)

        result = store.check_budget("eng")
        assert result["within_budget"] is False
        assert result["pct_used"] == 150.0

        budget = store.get_budget("eng")
        assert budget is not None
        assert budget.is_exceeded is True

    def test_check_budget_no_budget(self, store: CostStore) -> None:
        result = store.check_budget("nonexistent")
        assert result["within_budget"] is True
        assert result["has_budget"] is False

    def test_update_budget(self, store: CostStore) -> None:
        store.create_budget(team="eng", monthly_limit_usd=100.0)
        updated = store.update_budget("eng", monthly_limit_usd=200.0)
        assert updated is not None
        assert updated.monthly_limit_usd == 200.0

    def test_list_budgets(self, store: CostStore) -> None:
        store.create_budget(team="eng", monthly_limit_usd=100.0)
        store.create_budget(team="sales", monthly_limit_usd=50.0)
        budgets = store.list_budgets()
        assert len(budgets) == 2
        # Sorted by team name
        assert budgets[0].team == "eng"
        assert budgets[1].team == "sales"


# ---------------------------------------------------------------------------
# Model Comparison Tests
# ---------------------------------------------------------------------------


class TestCompareModels:
    def test_compare_models(self, store: CostStore) -> None:
        result = store.compare_models("gpt-4o", "claude-haiku-4.5", 1_000_000)
        assert result["model_a"] == "gpt-4o"
        assert result["model_b"] == "claude-haiku-4.5"
        assert result["model_a_cost"] > 0
        assert result["model_b_cost"] > 0
        assert result["sample_tokens"] == 1_000_000

        # claude-haiku-4.5 should be cheaper than gpt-4o
        # gpt-4o: (0.5M * 2.50 + 0.5M * 10.00) / 1M = 6.25
        # haiku: (0.5M * 0.80 + 0.5M * 4.00) / 1M = 2.40
        assert result["model_b_cost"] < result["model_a_cost"]
        assert result["savings_pct"] > 0

    def test_compare_unknown_model(self, store: CostStore) -> None:
        result = store.compare_models("gpt-4o", "unknown-model", 1_000_000)
        assert result["model_b_cost"] == 0.0


# ---------------------------------------------------------------------------
# Top Spenders Tests
# ---------------------------------------------------------------------------


class TestTopSpenders:
    def test_top_spenders(self, store: CostStore) -> None:
        _record(store, agent_name="agent-a", cost_usd=10.0, team="eng")
        _record(store, agent_name="agent-b", cost_usd=5.0, team="sales")
        _record(store, agent_name="agent-c", cost_usd=20.0, team="eng")

        spenders = store.get_top_spenders(limit=2)
        assert len(spenders) == 2
        assert spenders[0]["agent_name"] == "agent-c"
        assert spenders[0]["cost"] == 20.0
        assert spenders[1]["agent_name"] == "agent-a"
        assert spenders[1]["cost"] == 10.0

    def test_top_spenders_empty(self, store: CostStore) -> None:
        spenders = store.get_top_spenders()
        assert spenders == []
