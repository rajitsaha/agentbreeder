"""Tests for the tracing service — traces, spans, metrics, search, and deletion."""

from __future__ import annotations

import pytest

from api.services.tracing_service import TracingStore, _percentile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store_with_traces(count: int = 3) -> TracingStore:
    """Create a store pre-populated with test traces."""
    store = TracingStore()
    for i in range(count):
        status = "error" if i == 0 else "success"
        store.create_trace(
            trace_id=f"trace-{i}",
            agent_name="test-agent" if i < 2 else "other-agent",
            status=status,
            duration_ms=(i + 1) * 100,
            total_tokens=(i + 1) * 500,
            input_tokens=(i + 1) * 200,
            output_tokens=(i + 1) * 300,
            cost_usd=(i + 1) * 0.01,
            model_name="claude-sonnet-4",
            input_preview=f"Input for trace {i}",
            output_preview=f"Output for trace {i}",
            error_message="Something went wrong" if i == 0 else None,
            metadata={"env": "test", "index": i},
        )
    return store


# ---------------------------------------------------------------------------
# Trace CRUD Tests
# ---------------------------------------------------------------------------


class TestCreateTrace:
    def test_create_trace_basic(self):
        store = TracingStore()
        trace = store.create_trace(
            trace_id="abc-123",
            agent_name="my-agent",
        )
        assert trace.trace_id == "abc-123"
        assert trace.agent_name == "my-agent"
        assert trace.status == "success"
        assert trace.duration_ms == 0
        assert trace.created_at != ""

    def test_create_trace_with_all_fields(self):
        store = TracingStore()
        trace = store.create_trace(
            trace_id="full-trace",
            agent_name="agent-x",
            agent_id="agent-uuid-1",
            status="error",
            duration_ms=1500,
            total_tokens=2000,
            input_tokens=800,
            output_tokens=1200,
            cost_usd=0.025,
            model_name="gpt-4o",
            input_preview="Hello, world",
            output_preview="Hi there!",
            error_message="Timeout occurred",
            metadata={"run_id": "r1"},
        )
        assert trace.status == "error"
        assert trace.duration_ms == 1500
        assert trace.total_tokens == 2000
        assert trace.cost_usd == 0.025
        assert trace.model_name == "gpt-4o"
        assert trace.error_message == "Timeout occurred"
        assert trace.metadata == {"run_id": "r1"}

    def test_create_trace_truncates_preview(self):
        store = TracingStore()
        long_input = "x" * 500
        trace = store.create_trace(
            trace_id="trunc-test",
            agent_name="agent",
            input_preview=long_input,
        )
        assert trace.input_preview is not None
        assert len(trace.input_preview) == 200

    def test_create_trace_generates_unique_id(self):
        store = TracingStore()
        t1 = store.create_trace(trace_id="t1", agent_name="a")
        t2 = store.create_trace(trace_id="t2", agent_name="a")
        assert t1.id != t2.id


class TestGetTrace:
    def test_get_existing_trace(self):
        store = make_store_with_traces(1)
        trace = store.get_trace("trace-0")
        assert trace is not None
        assert trace.trace_id == "trace-0"

    def test_get_nonexistent_trace(self):
        store = TracingStore()
        assert store.get_trace("does-not-exist") is None


# ---------------------------------------------------------------------------
# Span CRUD Tests
# ---------------------------------------------------------------------------


class TestCreateSpan:
    def test_create_span_basic(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="agent")
        span = store.create_span(
            trace_id="t1",
            span_id="s1",
            name="llm.chat",
            span_type="llm",
        )
        assert span.span_id == "s1"
        assert span.name == "llm.chat"
        assert span.span_type == "llm"
        assert span.status == "success"

    def test_create_span_with_full_data(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="agent")
        span = store.create_span(
            trace_id="t1",
            span_id="s1",
            name="tool.execute",
            span_type="tool",
            parent_span_id=None,
            status="error",
            duration_ms=300,
            input_data={"query": "search term"},
            output_data={"results": [1, 2, 3]},
            model_name=None,
            input_tokens=50,
            output_tokens=100,
            cost_usd=0.001,
            metadata={"tool_name": "search"},
            started_at="2025-01-01T00:00:00",
            ended_at="2025-01-01T00:00:01",
        )
        assert span.status == "error"
        assert span.duration_ms == 300
        assert span.input_data == {"query": "search term"}
        assert span.cost_usd == 0.001

    def test_create_span_raises_for_missing_trace(self):
        store = TracingStore()
        with pytest.raises(ValueError, match="not found"):
            store.create_span(
                trace_id="nonexistent",
                span_id="s1",
                name="test",
            )

    def test_create_multiple_spans(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="agent")
        store.create_span(trace_id="t1", span_id="s1", name="step1")
        store.create_span(trace_id="t1", span_id="s2", name="step2", parent_span_id="s1")
        store.create_span(trace_id="t1", span_id="s3", name="step3", parent_span_id="s1")

        spans = store.get_trace_spans("t1")
        assert len(spans) == 3


class TestGetTraceWithSpans:
    def test_get_trace_with_spans(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="agent")
        store.create_span(trace_id="t1", span_id="s1", name="root", span_type="agent")
        store.create_span(
            trace_id="t1",
            span_id="s2",
            name="llm_call",
            span_type="llm",
            parent_span_id="s1",
        )

        trace = store.get_trace("t1")
        spans = store.get_trace_spans("t1")

        assert trace is not None
        assert len(spans) == 2
        assert spans[0].span_id == "s1"
        assert spans[1].span_id == "s2"

    def test_get_spans_for_nonexistent_trace(self):
        store = TracingStore()
        spans = store.get_trace_spans("nope")
        assert spans == []


# ---------------------------------------------------------------------------
# List & Filter Tests
# ---------------------------------------------------------------------------


class TestListTracesWithFilters:
    def test_list_all_traces(self):
        store = make_store_with_traces(5)
        traces, total = store.list_traces()
        assert total == 5
        assert len(traces) == 5

    def test_list_with_pagination(self):
        store = make_store_with_traces(5)
        traces, total = store.list_traces(page=1, per_page=2)
        assert total == 5
        assert len(traces) == 2

        traces2, _ = store.list_traces(page=2, per_page=2)
        assert len(traces2) == 2

        traces3, _ = store.list_traces(page=3, per_page=2)
        assert len(traces3) == 1

    def test_filter_by_agent_name(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(agent_name="test-agent")
        assert total == 2
        assert all(t.agent_name == "test-agent" for t in traces)

    def test_filter_by_status(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(status="error")
        assert total == 1
        assert traces[0].status == "error"

    def test_filter_by_min_duration(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(min_duration=200)
        assert total == 2
        assert all(t.duration_ms >= 200 for t in traces)

    def test_filter_by_min_cost(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(min_cost=0.02)
        assert total == 2
        assert all(t.cost_usd >= 0.02 for t in traces)

    def test_combined_filters(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(
            agent_name="test-agent",
            status="success",
        )
        assert total == 1
        assert traces[0].agent_name == "test-agent"
        assert traces[0].status == "success"

    def test_empty_result(self):
        store = make_store_with_traces(3)
        traces, total = store.list_traces(agent_name="nonexistent")
        assert total == 0
        assert traces == []

    def test_ordered_by_created_at_descending(self):
        store = make_store_with_traces(3)
        traces, _ = store.list_traces()
        for i in range(len(traces) - 1):
            assert traces[i].created_at >= traces[i + 1].created_at


# ---------------------------------------------------------------------------
# Metrics Tests
# ---------------------------------------------------------------------------


class TestGetAgentMetrics:
    def test_metrics_for_existing_agent(self):
        store = make_store_with_traces(3)
        metrics = store.get_agent_metrics("test-agent")

        assert metrics["agent_name"] == "test-agent"
        assert metrics["request_count"] == 2
        assert metrics["error_count"] == 1  # trace-0 is error
        assert metrics["total_tokens"] == 500 + 1000  # 1*500 + 2*500
        assert metrics["total_cost_usd"] > 0
        assert metrics["avg_duration_ms"] > 0
        assert metrics["p50_duration_ms"] > 0
        assert metrics["p95_duration_ms"] > 0
        assert metrics["p99_duration_ms"] > 0

    def test_metrics_for_nonexistent_agent(self):
        store = TracingStore()
        metrics = store.get_agent_metrics("nobody")

        assert metrics["agent_name"] == "nobody"
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["avg_duration_ms"] == 0.0
        assert metrics["total_tokens"] == 0
        assert metrics["total_cost_usd"] == 0.0

    def test_metrics_single_trace(self):
        store = TracingStore()
        store.create_trace(
            trace_id="t1",
            agent_name="solo",
            duration_ms=500,
            total_tokens=1000,
            cost_usd=0.05,
        )
        metrics = store.get_agent_metrics("solo")
        assert metrics["request_count"] == 1
        assert metrics["avg_duration_ms"] == 500.0
        assert metrics["p50_duration_ms"] == 500.0
        assert metrics["p95_duration_ms"] == 500.0
        assert metrics["p99_duration_ms"] == 500.0


# ---------------------------------------------------------------------------
# Search Tests
# ---------------------------------------------------------------------------


class TestSearchTraces:
    def test_search_by_agent_name(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("test-agent")
        assert total == 2

    def test_search_by_input_preview(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("Input for trace 2")
        assert total == 1
        assert results[0].trace_id == "trace-2"

    def test_search_by_error_message(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("Something went wrong")
        assert total == 1
        assert results[0].status == "error"

    def test_search_by_trace_id(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("trace-1")
        assert total == 1

    def test_search_case_insensitive(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("TEST-AGENT")
        assert total == 2

    def test_search_with_filters(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces(
            "test-agent",
            status="error",
        )
        assert total == 1

    def test_search_no_results(self):
        store = make_store_with_traces(3)
        results, total = store.search_traces("zzz-no-match")
        assert total == 0
        assert results == []

    def test_search_with_pagination(self):
        store = make_store_with_traces(5)
        results, total = store.search_traces("agent", page=1, per_page=2)
        assert total == 5
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Delete Tests
# ---------------------------------------------------------------------------


class TestDeleteOldTraces:
    def test_delete_traces_before_date(self):
        store = make_store_with_traces(3)

        # All traces have created_at ~ now, so a future date should delete all
        count = store.delete_traces("9999-12-31T23:59:59")
        assert count == 3
        traces, total = store.list_traces()
        assert total == 0

    def test_delete_no_matching_traces(self):
        store = make_store_with_traces(3)

        # A very old date should delete nothing
        count = store.delete_traces("2000-01-01T00:00:00")
        assert count == 0
        traces, total = store.list_traces()
        assert total == 3

    def test_delete_also_removes_spans(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="a")
        store.create_span(trace_id="t1", span_id="s1", name="test")

        count = store.delete_traces("9999-12-31T23:59:59")
        assert count == 1
        assert store.get_trace_spans("t1") == []


# ---------------------------------------------------------------------------
# Timeline (Span Tree) Tests
# ---------------------------------------------------------------------------


class TestTraceTimeline:
    def test_flat_spans(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="a")
        store.create_span(trace_id="t1", span_id="s1", name="step1")
        store.create_span(trace_id="t1", span_id="s2", name="step2")

        timeline = store.get_trace_timeline("t1")
        assert len(timeline) == 2
        assert timeline[0]["children"] == []

    def test_nested_spans(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="a")
        store.create_span(trace_id="t1", span_id="root", name="root", span_type="agent")
        store.create_span(
            trace_id="t1",
            span_id="child1",
            name="llm_call",
            span_type="llm",
            parent_span_id="root",
        )
        store.create_span(
            trace_id="t1",
            span_id="child2",
            name="tool_exec",
            span_type="tool",
            parent_span_id="root",
        )
        store.create_span(
            trace_id="t1",
            span_id="grandchild",
            name="sub_step",
            span_type="custom",
            parent_span_id="child1",
        )

        timeline = store.get_trace_timeline("t1")
        assert len(timeline) == 1  # one root
        root = timeline[0]
        assert root["span_id"] == "root"
        assert len(root["children"]) == 2
        # child1 should have grandchild
        child1 = next(c for c in root["children"] if c["span_id"] == "child1")
        assert len(child1["children"]) == 1
        assert child1["children"][0]["span_id"] == "grandchild"

    def test_empty_timeline(self):
        store = TracingStore()
        store.create_trace(trace_id="t1", agent_name="a")
        timeline = store.get_trace_timeline("t1")
        assert timeline == []

    def test_nonexistent_trace_timeline(self):
        store = TracingStore()
        timeline = store.get_trace_timeline("nope")
        assert timeline == []


# ---------------------------------------------------------------------------
# Percentile Helper Tests
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_empty_list(self):
        assert _percentile([], 50) == 0.0

    def test_single_value(self):
        assert _percentile([100], 50) == 100.0
        assert _percentile([100], 99) == 100.0

    def test_p50(self):
        values = sorted([10, 20, 30, 40, 50])
        p50 = _percentile(values, 50)
        assert p50 == 30.0

    def test_p95(self):
        values = sorted(range(1, 101))
        p95 = _percentile(values, 95)
        assert p95 == pytest.approx(95.05, abs=0.1)

    def test_p99(self):
        values = sorted(range(1, 101))
        p99 = _percentile(values, 99)
        assert p99 == pytest.approx(99.01, abs=0.1)
