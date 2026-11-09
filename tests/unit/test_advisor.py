import asyncio

import pytest

from frostwatch.analysis.advisor import (
    AuditInputs,
    AuditResult,
    analyze,
    collect_inputs,
    credits_per_hour,
    next_size_down,
    normalize_size,
)
from frostwatch.analysis.audit_report import render_html, render_markdown
from frostwatch.demo.audit_demo import demo_inputs


def _ids(result):
    return [(f.check_id, f.object_name) for f in result.findings]


def test_size_helpers():
    assert normalize_size("X-Small") == "XSMALL"
    assert normalize_size("2X-Large") == "2XLARGE"
    assert normalize_size("XXLARGE") == "2XLARGE"
    assert credits_per_hour("Medium") == 4
    assert next_size_down("Large") == "MEDIUM"
    assert next_size_down("X-Small") is None


def test_auto_suspend_high_estimate():
    inp = AuditInputs(
        warehouses=[{"NAME": "WH", "SIZE": "Large", "AUTO_SUSPEND": 600}],
        metering=[{"WAREHOUSE_NAME": "WH", "CREDITS": 1000, "ACTIVE_HOURS": 300}],
        resumes=[{"WAREHOUSE_NAME": "WH", "RESUMES": 100}],
    )
    r = analyze(inp, days=30, credit_price=3.0)
    f = next(f for f in r.findings if f.check_id == "auto_suspend_high")
    # (600 - 60)s * 100 resumes = 15h idle * 8 credits/h * $3 = $360
    assert f.monthly_savings_usd == pytest.approx(360.0)
    assert "SET AUTO_SUSPEND = 60" in f.fix_sql


def test_auto_suspend_ok_is_silent():
    inp = AuditInputs(
        warehouses=[{"name": "WH", "size": "Small", "auto_suspend": 60}],
        metering=[{"warehouse_name": "WH", "credits": 100, "active_hours": 100}],
    )
    assert not [f for f in analyze(inp).findings if f.check_id.startswith("auto_suspend")]


def test_window_scaling_to_month():
    inp = AuditInputs(
        warehouses=[{"name": "WH", "size": "Large", "auto_suspend": 600}],
        metering=[{"warehouse_name": "WH", "credits": 1000, "active_hours": 300}],
        resumes=[{"warehouse_name": "WH", "resumes": 50}],
    )
    # 15 days of data scales x2 to a month: 7.5h * 8 * 3 * 2 = $360
    r = analyze(inp, days=15, credit_price=3.0)
    assert r.findings[0].monthly_savings_usd == pytest.approx(360.0)


def test_compute_savings_capped_per_warehouse():
    r = analyze(demo_inputs(), days=30, credit_price=3.0)
    by_obj: dict[str, float] = {}
    cost: dict[str, float] = {}
    for f in r.findings:
        if f.category == "compute" and f.monthly_cost_usd:
            by_obj[f.object_name] = by_obj.get(f.object_name, 0) + f.monthly_savings_usd
            cost[f.object_name] = f.monthly_cost_usd
    for name, total in by_obj.items():
        assert total <= cost[name] * 0.7 + 0.01


def test_demo_covers_every_check_and_sorts():
    r = analyze(demo_inputs(), days=30, credit_price=3.0, demo=True)
    checks = {f.check_id for f in r.findings}
    assert {
        "auto_suspend_disabled",
        "auto_suspend_high",
        "oversized_warehouse",
        "remote_spilling",
        "queuing",
        "repeated_query",
        "cloud_services_billed",
        "time_travel_storage",
        "unused_table",
        "no_resource_monitor",
        "auto_clustering_cost",
    } <= checks
    savings = [f.monthly_savings_usd for f in r.findings]
    assert savings == sorted(savings, reverse=True)
    assert r.monthly_savings_usd == pytest.approx(sum(savings), abs=0.05)


def test_roundtrip_and_render():
    r = analyze(demo_inputs(), demo=True)
    r2 = AuditResult.from_dict(r.to_dict())
    assert _ids(r2) == _ids(r)
    html = render_html(r2)
    assert "Snowflake Savings Audit" in html and "DEMO DATA" in html
    assert "<script>alert" not in render_html(
        analyze(
            AuditInputs(
                unused_tables=[
                    {
                        "table_catalog": "<script>alert(1)</script>",
                        "table_schema": "S",
                        "table_name": "T",
                        "active_bytes": 10 * 1024**4,
                    }
                ]
            )
        )
    )
    md = render_markdown(r2)
    assert md.startswith("# Snowflake Savings Audit")


def test_collect_inputs_isolates_failures():
    class Fake:
        async def execute(self, sql, params=None):
            if "ACCESS_HISTORY" in sql:
                raise RuntimeError("Object does not exist")
            if sql == "SHOW WAREHOUSES":
                assert params is None
                return [{"name": "WH", "size": "Small", "auto_suspend": 60}]
            assert params == {"days": 30}
            return []

    inp = asyncio.run(collect_inputs(Fake(), 30))
    assert inp.warehouses[0]["name"] == "WH"
    assert "unused_tables" in inp.skipped
    assert "Enterprise" in inp.skipped["unused_tables"]
