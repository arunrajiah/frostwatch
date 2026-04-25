from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select

from frostwatch.api.models import AnomalyResponse
from frostwatch.core.db import AnomalyRecord, get_db

router = APIRouter()


@router.get("/anomalies", response_model=list[AnomalyResponse])
async def get_anomalies(
    days: int = Query(default=30, ge=1, le=365),
) -> list[AnomalyResponse]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with get_db() as session:
            result = await session.execute(
                select(AnomalyRecord)
                .where(AnomalyRecord.detected_at >= cutoff)
                .order_by(desc(AnomalyRecord.detected_at))
            )
            rows = result.scalars().all()

        return [
            AnomalyResponse(
                id=row.id,
                detected_at=row.detected_at,
                anomaly_type=row.anomaly_type,
                warehouse_name=row.warehouse_name,
                severity=row.severity,
                description=row.description,
                llm_explanation=row.llm_explanation,
            )
            for row in rows
        ]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
