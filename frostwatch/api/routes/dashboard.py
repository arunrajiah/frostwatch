from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select

from frostwatch.api.models import (
    AnomalyResponse,
    CostBreakdownItem,
    DashboardSummary,
)
from frostwatch.core.db import AnomalyRecord, CachedQuery, CachedWarehouseMetric, SyncRun, get_db

router = APIRouter()


@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(request: Request) -> DashboardSummary:
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar

    now = datetime.now(UTC)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    try:
        async with get_db() as session:
            q7_result = await session.execute(
                select(CachedQuery).where(CachedQuery.start_time >= cutoff_7d)
            )
            queries_7d = q7_result.scalars().all()

            wm_result = await session.execute(
                select(CachedWarehouseMetric).where(CachedWarehouseMetric.date >= cutoff_30d.date())
            )
            all_metrics = wm_result.scalars().all()

            wm7_result = await session.execute(
                select(CachedWarehouseMetric).where(CachedWarehouseMetric.date >= cutoff_7d.date())
            )
            metrics_7d = wm7_result.scalars().all()

            anomaly_result = await session.execute(
                select(AnomalyRecord)
                .where(AnomalyRecord.detected_at >= cutoff_30d)
                .order_by(desc(AnomalyRecord.detected_at))
                .limit(10)
            )
            recent_anomalies = anomaly_result.scalars().all()

            sync_result = await session.execute(
                select(SyncRun)
                .where(SyncRun.status == "success")
                .order_by(desc(SyncRun.finished_at))
                .limit(1)
            )
            last_sync = sync_result.scalar_one_or_none()

        total_credits_7d = sum(float(m.credits_used or 0) for m in metrics_7d)
        total_cost_7d = total_credits_7d / credits_per_dollar if credits_per_dollar else 0.0

        total_credits_30d = sum(float(m.credits_used or 0) for m in all_metrics)
        total_cost_30d = total_credits_30d / credits_per_dollar if credits_per_dollar else 0.0

        wh_credits: dict[str, float] = defaultdict(float)
        for m in all_metrics:
            wh_credits[m.warehouse_name] += float(m.credits_used or 0)

        top_warehouses = [
            CostBreakdownItem(
                name=name,
                credits=round(credits, 4),
                cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
                pct_of_total=round(credits / total_credits_30d * 100, 2)
                if total_credits_30d
                else 0.0,
            )
            for name, credits in sorted(wh_credits.items(), key=lambda x: -x[1])[:5]
        ]

        user_credits: dict[str, float] = defaultdict(float)
        for q in queries_7d:
            user = q.user_name or "UNKNOWN"
            user_credits[user] += float(q.credits_used or 0)

        user_total = sum(user_credits.values()) or 1.0
        top_users = [
            CostBreakdownItem(
                name=name,
                credits=round(credits, 4),
                cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
                pct_of_total=round(credits / user_total * 100, 2),
            )
            for name, credits in sorted(user_credits.items(), key=lambda x: -x[1])[:5]
        ]

        anomaly_responses = [
            AnomalyResponse(
                id=a.id,
                detected_at=a.detected_at,
                anomaly_type=a.anomaly_type,
                warehouse_name=a.warehouse_name,
                severity=a.severity,
                description=a.description,
                llm_explanation=a.llm_explanation,
            )
            for a in recent_anomalies
        ]

        return DashboardSummary(
            total_credits_7d=round(total_credits_7d, 4),
            total_cost_7d=round(total_cost_7d, 4),
            total_credits_30d=round(total_credits_30d, 4),
            total_cost_30d=round(total_cost_30d, 4),
            top_warehouses=top_warehouses,
            top_users=top_users,
            recent_anomalies=anomaly_responses,
            last_synced=last_sync.finished_at if last_sync else None,
            query_count_7d=len(queries_7d),
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
