"""Resource monitor API routes — recommendations, proximity alerts, budget tracking."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from frostwatch.analysis.resource_monitors import (
    compute_budget_usage,
    detect_proximity_alerts,
    generate_monitor_sql,
    recommend_monitors,
)
from frostwatch.api.limiter import limiter
from frostwatch.api.models import (
    BudgetSummary,
    BudgetUsageRecord,
    GenerateSqlResponse,
    MonitorRecommendationRecord,
    ProximityAlertRecord,
    ResourceMonitorRecord,
)
from frostwatch.core.db import CachedQuery, CachedWarehouseMetric, ResourceMonitor, get_db

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_warehouses(raw: str | None) -> list[str]:
    """Parse a JSON-encoded warehouse list, falling back gracefully."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [str(w) for w in parsed] if isinstance(parsed, list) else []
    except Exception:
        return [w.strip() for w in raw.split(",") if w.strip()]


def _monitor_to_record(m: ResourceMonitor) -> ResourceMonitorRecord:
    return ResourceMonitorRecord(
        id=m.id,
        name=m.name,
        credit_quota=m.credit_quota,
        used_credits=m.used_credits,
        remaining_credits=m.remaining_credits,
        level=m.level,
        frequency=m.frequency,
        notify_at_percentage=m.notify_at_percentage,
        suspend_at_percentage=m.suspend_at_percentage,
        suspend_immediately_at_percentage=m.suspend_immediately_at_percentage,
        warehouses=_parse_warehouses(m.warehouses),
        owner=m.owner,
        synced_at=m.synced_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/resource-monitors", response_model=list[ResourceMonitorRecord])
@limiter.limit("60/minute")
async def list_resource_monitors(request: Request) -> list[ResourceMonitorRecord]:
    """Return all resource monitors cached from Snowflake ACCOUNT_USAGE."""
    try:
        async with get_db() as session:
            result = await session.execute(select(ResourceMonitor).order_by(ResourceMonitor.name))
            monitors = result.scalars().all()
        return [_monitor_to_record(m) for m in monitors]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/resource-monitors/recommendations", response_model=list[MonitorRecommendationRecord])
@limiter.limit("30/minute")
async def get_monitor_recommendations(
    request: Request,
    history_days: int = Query(30, ge=7, le=90, description="Days of history to use"),
    buffer_pct: float = Query(0.20, ge=0.0, le=1.0, description="Overhead buffer fraction"),
) -> list[MonitorRecommendationRecord]:
    """Analyse per-warehouse spend and recommend resource monitor quotas.

    Uses p95 daily credits over *history_days* to suggest a monthly quota
    with a *buffer_pct* overhead. Also compares against any existing monitors
    to flag under- or over-sized quotas.
    """
    try:
        config = request.app.state.config

        async with get_db() as session:
            wm_result = await session.execute(select(CachedWarehouseMetric))
            metrics = [
                {c.name: getattr(row, c.name) for c in CachedWarehouseMetric.__table__.columns}
                for row in wm_result.scalars().all()
            ]

            mon_result = await session.execute(select(ResourceMonitor))
            monitors = [
                {c.name: getattr(row, c.name) for c in ResourceMonitor.__table__.columns}
                for row in mon_result.scalars().all()
            ]

        recs = recommend_monitors(
            warehouse_metrics=metrics,
            existing_monitors=monitors,
            credits_per_dollar=config.credits_per_dollar,
            history_days=history_days,
            buffer_pct=buffer_pct,
        )
        return [MonitorRecommendationRecord(**r) for r in recs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/resource-monitors/generate-sql", response_model=GenerateSqlResponse)
@limiter.limit("30/minute")
async def generate_sql_for_warehouse(
    request: Request,
    warehouse: str = Query(..., description="Warehouse name to generate DDL for"),
    history_days: int = Query(30, ge=7, le=90),
    buffer_pct: float = Query(0.20, ge=0.0, le=1.0),
) -> GenerateSqlResponse:
    """Generate a ``CREATE OR REPLACE RESOURCE MONITOR`` DDL statement for a warehouse.

    The SQL is copy-paste ready for a Snowflake worksheet. Inline comments
    explain each clause and include the supporting statistics.
    """
    try:
        config = request.app.state.config

        async with get_db() as session:
            wm_result = await session.execute(select(CachedWarehouseMetric))
            metrics = [
                {c.name: getattr(row, c.name) for c in CachedWarehouseMetric.__table__.columns}
                for row in wm_result.scalars().all()
            ]

            mon_result = await session.execute(select(ResourceMonitor))
            monitors = [
                {c.name: getattr(row, c.name) for c in ResourceMonitor.__table__.columns}
                for row in mon_result.scalars().all()
            ]

        recs = recommend_monitors(
            warehouse_metrics=metrics,
            existing_monitors=monitors,
            credits_per_dollar=config.credits_per_dollar,
            history_days=history_days,
            buffer_pct=buffer_pct,
        )

        rec = next((r for r in recs if r["warehouse_name"].lower() == warehouse.lower()), None)
        if rec is None:
            raise HTTPException(
                status_code=404,
                detail=f"No usage data found for warehouse '{warehouse}'",
            )

        sql = generate_monitor_sql(rec)
        monitor_name = f"RM_{warehouse.upper()}"
        return GenerateSqlResponse(
            warehouse_name=rec["warehouse_name"],
            monitor_name=monitor_name,
            sql=sql,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/resource-monitors/proximity-alerts", response_model=list[ProximityAlertRecord])
@limiter.limit("60/minute")
async def get_proximity_alerts(request: Request) -> list[ProximityAlertRecord]:
    """Return monitors that are close to a trigger threshold.

    Severity levels:
    - **critical** — within 5 percentage points of a trigger
    - **high** — within 15 percentage points of a trigger
    - **medium** — beyond 15 pp but has a trigger threshold ahead
    """
    try:
        async with get_db() as session:
            result = await session.execute(select(ResourceMonitor))
            monitors = [
                {c.name: getattr(row, c.name) for c in ResourceMonitor.__table__.columns}
                for row in result.scalars().all()
            ]

        alerts = detect_proximity_alerts(monitors)
        out = []
        for a in alerts:
            wh_raw = a.get("warehouse_names", "[]")
            wh_list = _parse_warehouses(wh_raw if isinstance(wh_raw, str) else json.dumps(wh_raw))
            out.append(
                ProximityAlertRecord(
                    monitor_name=a.get("monitor_name"),
                    warehouse_names=wh_list,
                    credit_quota=a["credit_quota"],
                    used_credits=a["used_credits"],
                    remaining_credits=a["remaining_credits"],
                    used_pct=a["used_pct"],
                    nearest_trigger=a.get("nearest_trigger"),
                    nearest_trigger_pct=a.get("nearest_trigger_pct"),
                    margin_to_trigger_ppt=a.get("margin_to_trigger_ppt"),
                    frequency=a.get("frequency"),
                    severity=a["severity"],
                )
            )
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/resource-monitors/budgets", response_model=BudgetSummary)
@limiter.limit("60/minute")
async def get_budget_usage(
    request: Request,
    days: int = Query(1, ge=1, le=30, description="Number of days to include in the window"),
) -> BudgetSummary:
    """Return per-user and per-role credit spend vs configured daily budgets.

    Budgets are configured in ``user_credit_budgets`` and ``role_credit_budgets``
    in your FrostWatch config. Returns all budgeted entities plus any
    unbudgeted users/roles that had spend in the period.
    """
    try:
        config = request.app.state.config
        user_budgets: dict[str, float] = config.user_credit_budgets or {}
        role_budgets: dict[str, float] = config.role_credit_budgets or {}

        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with get_db() as session:
            result = await session.execute(
                select(CachedQuery).where(CachedQuery.start_time >= cutoff)
            )
            queries = [
                {c.name: getattr(row, c.name) for c in CachedQuery.__table__.columns}
                for row in result.scalars().all()
            ]

        usage = compute_budget_usage(queries, user_budgets, role_budgets, days=days)

        def _to_records(rows: list[dict]) -> list[BudgetUsageRecord]:
            return [BudgetUsageRecord(**r) for r in rows]

        return BudgetSummary(
            days=days,
            users=_to_records(usage["users"]),
            roles=_to_records(usage["roles"]),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
