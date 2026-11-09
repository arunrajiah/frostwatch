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


async def save_audit(result: AuditResult, generated_at: datetime | None = None) -> int:
    if generated_at is not None:
        result.generated_at = generated_at.isoformat(timespec="seconds")
    async with get_db() as session:
        run = AdvisorRun(
            generated_at=generated_at or datetime.now(UTC),
            monthly_savings_usd=result.monthly_savings_usd,
            result_json=json.dumps(result.to_dict()),
        )
        session.add(run)
        await session.flush()
        return run.id


async def _recent(n: int) -> list[AuditResult]:
    async with get_db() as session:
        rows = (
            (
                await session.execute(
                    select(AdvisorRun).order_by(AdvisorRun.generated_at.desc()).limit(n)
                )
            )
            .scalars()
            .all()
        )
    return [AuditResult.from_dict(json.loads(r.result_json)) for r in rows]


async def _latest() -> AuditResult | None:
    runs = await _recent(1)
    return runs[0] if runs else None


def compare_audits(latest: AuditResult, previous: AuditResult | None) -> dict:
    """What changed since the previous audit: fixed findings and new ones."""
    if previous is None:
        return {
            "previous_generated_at": None,
            "resolved": [],
            "new_count": 0,
            "savings_captured_usd": 0.0,
        }

    # Grouped findings (one row listing many warehouses) are matched by check only,
    # so a shorter list is not reported as "fixed".
    grouped = {"no_resource_monitor"}

    def key(f) -> tuple[str, str]:
        return (f.check_id, "" if f.check_id in grouped else f.object_name)

    now_keys = {key(f) for f in latest.findings}
    before_keys = {key(f) for f in previous.findings}
    resolved = [f for f in previous.findings if key(f) not in now_keys]
    return {
        "previous_generated_at": previous.generated_at,
        "resolved": [
            {
                "title": f.title,
                "object_name": f.object_name,
                "monthly_savings_usd": f.monthly_savings_usd,
            }
            for f in resolved
        ],
        "new_count": len(now_keys - before_keys),
        "savings_captured_usd": round(sum(f.monthly_savings_usd for f in resolved), 2),
    }


@router.get("/advisor")
async def get_advisor() -> dict:
    """Latest Savings Advisor audit plus what changed since the previous one."""
    runs = await _recent(2)
    if not runs:
        return {"findings": [], "monthly_savings_usd": 0, "generated_at": None}
    out = runs[0].to_dict()
    out["changes"] = compare_audits(runs[0], runs[1] if len(runs) > 1 else None)
    return out


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
    previous = await _latest()
    await save_audit(result)
    out = result.to_dict()
    out["changes"] = compare_audits(result, previous)
    return out


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
