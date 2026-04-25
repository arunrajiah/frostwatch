from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import desc, select

from frostwatch.analysis.anomaly import detect_anomalies
from frostwatch.analysis.cost import compute_cost_breakdown
from frostwatch.analysis.recommendations import generate_report
from frostwatch.api.models import ReportResponse
from frostwatch.core.db import (
    AnomalyRecord,
    CachedQuery,
    CachedWarehouseMetric,
    ReportRecord,
    get_db,
)

router = APIRouter()


def _row_to_response(row: ReportRecord) -> ReportResponse:
    details = None
    if row.details_json:
        try:
            details = json.loads(row.details_json)
        except (json.JSONDecodeError, TypeError):
            details = row.details_json
    return ReportResponse(
        id=row.id,
        generated_at=row.generated_at,
        period_start=row.period_start,
        period_end=row.period_end,
        summary_text=row.summary_text,
        details_json=details,
    )


@router.get("/reports", response_model=list[ReportResponse])
async def list_reports() -> list[ReportResponse]:
    try:
        async with get_db() as session:
            result = await session.execute(
                select(ReportRecord).order_by(desc(ReportRecord.generated_at)).limit(50)
            )
            rows = result.scalars().all()
        return [_row_to_response(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reports/generate", response_model=ReportResponse, status_code=201)
async def generate_report_endpoint(request: Request) -> ReportResponse:
    config = request.app.state.config
    llm = request.app.state.llm_provider

    period_days = 7
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    try:
        async with get_db() as session:
            q_result = await session.execute(
                select(CachedQuery).where(CachedQuery.start_time >= period_start)
            )
            queries = [
                {c.name: getattr(row, c.name) for c in CachedQuery.__table__.columns}
                for row in q_result.scalars().all()
            ]

            wm_result = await session.execute(select(CachedWarehouseMetric))
            warehouse_metrics = [
                {
                    c.name: getattr(row, c.name)
                    for c in CachedWarehouseMetric.__table__.columns
                }
                for row in wm_result.scalars().all()
            ]

        cost_breakdown = compute_cost_breakdown(
            queries, warehouse_metrics, config.credits_per_dollar
        )
        anomalies = detect_anomalies(warehouse_metrics, config)
        anomaly_dicts = [a.model_dump() for a in anomalies]

        report_text = await generate_report(
            llm, queries, anomaly_dicts, cost_breakdown, period_days
        )

        details = {
            "cost_breakdown": cost_breakdown.model_dump(),
            "anomaly_count": len(anomalies),
            "query_count": len(queries),
        }

        new_report = ReportRecord(
            generated_at=now,
            period_start=period_start,
            period_end=now,
            summary_text=report_text,
            details_json=json.dumps(details),
        )

        async with get_db() as session:
            session.add(new_report)
            await session.flush()
            await session.refresh(new_report)
            report_id = new_report.id

        async with get_db() as session:
            result = await session.execute(
                select(ReportRecord).where(ReportRecord.id == report_id)
            )
            saved = result.scalar_one()
            return _row_to_response(saved)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int) -> ReportResponse:
    try:
        async with get_db() as session:
            result = await session.execute(
                select(ReportRecord).where(ReportRecord.id == report_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        return _row_to_response(row)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
