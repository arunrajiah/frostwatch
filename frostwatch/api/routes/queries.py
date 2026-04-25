from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import desc, select

from frostwatch.api.models import QueryRecord
from frostwatch.core.db import CachedQuery, get_db

router = APIRouter()


@router.get("/queries", response_model=list[QueryRecord])
async def get_queries(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[QueryRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with get_db() as session:
            result = await session.execute(
                select(CachedQuery)
                .where(CachedQuery.start_time >= cutoff)
                .order_by(desc(CachedQuery.credits_used))
                .limit(limit)
            )
            rows = result.scalars().all()

        return [
            QueryRecord(
                query_id=row.query_id,
                warehouse_name=row.warehouse_name,
                user_name=row.user_name,
                role_name=row.role_name,
                execution_time_ms=row.execution_time_ms,
                bytes_scanned=row.bytes_scanned,
                credits_used=row.credits_used,
                start_time=row.start_time,
                end_time=row.end_time,
                query_text_preview=(row.query_text or "")[:300],
                query_tag=row.query_tag,
                status=row.status,
            )
            for row in rows
        ]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
