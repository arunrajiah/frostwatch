"""Savings Advisor API: latest audit, run a new one, and download the report."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select

from frostwatch.analysis.advisor import AuditResult, run_audit
from frostwatch.analysis.audit_report import render_html, render_markdown
from frostwatch.api.limiter import limiter
from frostwatch.core.db import AdvisorRun, get_db

router = APIRouter()


async def save_audit(result: AuditResult) -> int:
    async with get_db() as session:
        run = AdvisorRun(
            generated_at=datetime.now(UTC),
            monthly_savings_usd=result.monthly_savings_usd,
            result_json=json.dumps(result.to_dict()),
        )
        session.add(run)
        await session.flush()
        return run.id


async def _latest() -> AuditResult | None:
    async with get_db() as session:
        row = (
            await session.execute(
                select(AdvisorRun).order_by(AdvisorRun.generated_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
    return AuditResult.from_dict(json.loads(row.result_json)) if row else None


@router.get("/advisor")
async def get_advisor() -> dict:
    """Latest Savings Advisor audit, or an empty result if none has run yet."""
    result = await _latest()
    if result is None:
        return {"findings": [], "monthly_savings_usd": 0, "generated_at": None}
    return result.to_dict()


@router.get("/advisor/history")
async def get_advisor_history(limit: int = 30) -> list[dict]:
    async with get_db() as session:
        rows = (
            await session.execute(
                select(AdvisorRun.generated_at, AdvisorRun.monthly_savings_usd)
                .order_by(AdvisorRun.generated_at.desc())
                .limit(min(limit, 365))
            )
        ).all()
    return [
        {"generated_at": r.generated_at.isoformat(), "monthly_savings_usd": r.monthly_savings_usd}
        for r in reversed(rows)
    ]


@router.post("/advisor/run")
@limiter.limit("3/minute")
async def run_advisor(request: Request, days: int = 30) -> dict:
    """Run a fresh audit against Snowflake (read-only, usually under a minute)."""
    from frostwatch.snowflake.client import SnowflakeClient

    config = request.app.state.config
    if not (config.snowflake_account or config.snowflake_connection_name):
        raise HTTPException(status_code=400, detail="Snowflake is not configured")
    client = SnowflakeClient(config)
    try:
        result = await run_audit(client, config, days=max(7, min(days, 365)))
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()
    await save_audit(result)
    return result.to_dict()


@router.get("/advisor/report.html", response_class=HTMLResponse)
async def advisor_report_html() -> HTMLResponse:
    result = await _latest()
    if result is None:
        raise HTTPException(status_code=404, detail="No audit yet")
    return HTMLResponse(
        render_html(result),
        headers={"Content-Disposition": 'inline; filename="frostwatch-audit.html"'},
    )


@router.get("/advisor/report.md", response_class=PlainTextResponse)
async def advisor_report_md() -> PlainTextResponse:
    result = await _latest()
    if result is None:
        raise HTTPException(status_code=404, detail="No audit yet")
    return PlainTextResponse(render_markdown(result), media_type="text/markdown")
