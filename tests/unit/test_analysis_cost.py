import pytest
from frostwatch.analysis.cost import compute_cost_breakdown


SAMPLE_QUERIES = [
    {"warehouse_name": "COMPUTE_WH", "user_name": "alice", "query_tag": "dbt", "credits_used": 2.0, "start_time": "2026-01-20"},
    {"warehouse_name": "COMPUTE_WH", "user_name": "bob",   "query_tag": "",    "credits_used": 1.0, "start_time": "2026-01-20"},
    {"warehouse_name": "REPORTING",  "user_name": "alice", "query_tag": "bi",  "credits_used": 3.0, "start_time": "2026-01-21"},
]

SAMPLE_METRICS = [
    {"warehouse_name": "COMPUTE_WH", "date": "2026-01-20", "credits_used": 3.0},
    {"warehouse_name": "REPORTING",  "date": "2026-01-21", "credits_used": 3.0},
]


def test_total_credits():
    result = compute_cost_breakdown(SAMPLE_QUERIES, SAMPLE_METRICS, credits_per_dollar=3.0)
    assert result.total_credits == pytest.approx(6.0)


def test_total_cost_usd():
    result = compute_cost_breakdown(SAMPLE_QUERIES, SAMPLE_METRICS, credits_per_dollar=3.0)
    assert result.total_cost_usd == pytest.approx(2.0)


def test_by_warehouse_sorted():
    result = compute_cost_breakdown(SAMPLE_QUERIES, SAMPLE_METRICS, credits_per_dollar=3.0)
    names = [w.name for w in result.by_warehouse]
    assert names[0] in {"COMPUTE_WH", "REPORTING"}
    assert len(result.by_warehouse) == 2


def test_by_user():
    result = compute_cost_breakdown(SAMPLE_QUERIES, SAMPLE_METRICS, credits_per_dollar=3.0)
    users = {u.name for u in result.by_user}
    assert "alice" in users
    assert "bob" in users


def test_pct_of_total_sums_to_100():
    result = compute_cost_breakdown(SAMPLE_QUERIES, SAMPLE_METRICS, credits_per_dollar=3.0)
    total_pct = sum(w.pct_of_total for w in result.by_warehouse)
    assert total_pct == pytest.approx(100.0, abs=0.1)


def test_empty_queries():
    result = compute_cost_breakdown([], [], credits_per_dollar=3.0)
    assert result.total_credits == 0.0
    assert result.total_cost_usd == 0.0
    assert result.by_warehouse == []
