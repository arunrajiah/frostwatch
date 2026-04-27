from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from frostwatch.api.models import DbtModelAgg
from frostwatch.core.db import CachedQuery, get_db

router = APIRouter()


@router.get("/dbt", response_model=list[DbtModelAgg])
async def get_dbt_breakdown(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
) -> list[DbtModelAgg]:
    """Return cost and performance breakdown by dbt model.

    Only queries whose query_tag contains a dbt node_id of the form
    ``model.<project>.<model_name>`` are included.
    """
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar
    cutoff = datetime.now(UTC) - timedelta(days=days)

    try:
        async with get_db() as session:
            result = await session.execute(
                select(CachedQuery).where(
                    CachedQuery.start_time >= cutoff,
                    CachedQuery.dbt_model.isnot(None),
                )
            )
            rows = result.scalars().all()

        model_credits: dict[str, float] = defaultdict(float)
        model_count: dict[str, int] = defaultdict(int)
        model_exec_ms: dict[str, float] = defaultdict(float)

        for q in rows:
            model = q.dbt_model or ""
            model_credits[model] += float(q.credits_used or 0)
            model_count[model] += 1
            model_exec_ms[model] += float(q.execution_time_ms or 0)

        results = [
            DbtModelAgg(
                dbt_model=model,
                total_credits=round(model_credits[model], 6),
                total_cost_usd=round(
                    model_credits[model] / credits_per_dollar if credits_per_dollar else 0, 4
                ),
                query_count=model_count[model],
                avg_execution_ms=round(
                    model_exec_ms[model] / model_count[model] if model_count[model] else 0, 2
                ),
            )
            for model in model_credits
        ]
        results.sort(key=lambda x: -x.total_credits)
        return results

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
