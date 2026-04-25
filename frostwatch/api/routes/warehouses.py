from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from frostwatch.api.models import WarehouseAgg, WarehouseMetric
from frostwatch.core.db import CachedQuery, CachedWarehouseMetric, get_db

router = APIRouter()


@router.get("/warehouses", response_model=list[WarehouseAgg])
async def get_warehouses(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
) -> list[WarehouseAgg]:
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar

    cutoff = datetime.now(UTC) - timedelta(days=days)

    try:
        async with get_db() as session:
            metrics_result = await session.execute(
                select(CachedWarehouseMetric).where(CachedWarehouseMetric.date >= cutoff.date())
            )
            metrics = metrics_result.scalars().all()

            queries_result = await session.execute(
                select(CachedQuery).where(CachedQuery.start_time >= cutoff)
            )
            queries = queries_result.scalars().all()

        wh_credits: dict[str, float] = defaultdict(float)
        for m in metrics:
            wh_credits[m.warehouse_name] += float(m.credits_used or 0)

        wh_query_count: dict[str, int] = defaultdict(int)
        wh_exec_ms_sum: dict[str, float] = defaultdict(float)
        for q in queries:
            wh = q.warehouse_name or "UNKNOWN"
            wh_query_count[wh] += 1
            wh_exec_ms_sum[wh] += float(q.execution_time_ms or 0)

        all_warehouses = set(wh_credits.keys()) | set(wh_query_count.keys())

        result = []
        for wh in sorted(all_warehouses):
            credits = wh_credits.get(wh, 0.0)
            count = wh_query_count.get(wh, 0)
            exec_sum = wh_exec_ms_sum.get(wh, 0.0)
            result.append(
                WarehouseAgg(
                    warehouse_name=wh,
                    total_credits=round(credits, 4),
                    total_cost_usd=round(
                        credits / credits_per_dollar if credits_per_dollar else 0, 4
                    ),
                    query_count=count,
                    avg_execution_ms=round(exec_sum / count if count else 0.0, 2),
                )
            )

        result.sort(key=lambda x: -x.total_credits)
        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/warehouses/timeseries", response_model=list[WarehouseMetric])
async def get_warehouse_timeseries(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    warehouse: str | None = Query(default=None),
) -> list[WarehouseMetric]:
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar

    cutoff = datetime.now(UTC) - timedelta(days=days)

    try:
        async with get_db() as session:
            query = select(CachedWarehouseMetric).where(CachedWarehouseMetric.date >= cutoff.date())
            if warehouse:
                query = query.where(CachedWarehouseMetric.warehouse_name == warehouse)
            result = await session.execute(query)
            rows = result.scalars().all()

        return [
            WarehouseMetric(
                warehouse_name=row.warehouse_name,
                date=row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
                credits_used=round(float(row.credits_used or 0), 4),
                cost_usd=round(
                    float(row.credits_used or 0) / credits_per_dollar if credits_per_dollar else 0,
                    4,
                ),
            )
            for row in sorted(rows, key=lambda r: (r.warehouse_name, r.date))
        ]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
