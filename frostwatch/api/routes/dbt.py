"""dbt integration routes — v0.1 model attribution + v0.3 dbt Cloud deep-dive.

Routes
------
GET  /api/dbt                      — Credit/cost breakdown by dbt model name
GET  /api/dbt/runs                 — dbt Cloud job runs with cost attribution
GET  /api/dbt/jobs                 — Cost breakdown by dbt Cloud job
GET  /api/dbt/environments         — Cost breakdown by dbt Cloud environment
GET  /api/dbt/threshold-alerts     — Models that exceeded their daily credit threshold
GET  /api/dbt/metadata             — Enriched model metadata (from manifest.json)
POST /api/dbt/sync-cloud           — Trigger a dbt Cloud metadata sync
POST /api/dbt/manifest             — Upload and parse a dbt manifest.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from frostwatch.api.models import (
    DbtCloudRunRecord,
    DbtCloudSyncResponse,
    DbtEnvironmentCostRecord,
    DbtJobCostRecord,
    DbtModelAgg,
    DbtModelMetadataRecord,
    DbtThresholdAlertRecord,
)
from frostwatch.core.db import (
    CachedQuery,
    DbtCloudRun,
    DbtModelMetadata,
    DbtModelThresholdAlert,
    get_db,
)

router = APIRouter()


# ── Existing: model attribution ───────────────────────────────────────────────


@router.get("/dbt", response_model=list[DbtModelAgg])
async def get_dbt_breakdown(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
) -> list[DbtModelAgg]:
    """Return credit and performance breakdown by dbt model name."""
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


# ── dbt Cloud runs ────────────────────────────────────────────────────────────


@router.get("/dbt/runs", response_model=list[DbtCloudRunRecord])
async def get_dbt_runs(
    days: int = Query(30, ge=1, le=90, description="Look-back window in days"),
    limit: int = Query(50, ge=1, le=200),
) -> list[DbtCloudRunRecord]:
    """Return dbt Cloud job runs stored by the last sync, newest first."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with get_db() as session:
        result = await session.execute(
            select(DbtCloudRun)
            .where(DbtCloudRun.started_at >= cutoff)
            .order_by(DbtCloudRun.started_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    return [
        DbtCloudRunRecord(
            id=r.id,
            run_id=r.run_id,
            job_id=r.job_id,
            job_name=r.job_name,
            environment_id=r.environment_id,
            environment_name=r.environment_name,
            project_id=r.project_id,
            project_name=r.project_name,
            triggered_by=r.triggered_by,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            duration_seconds=r.duration_seconds,
            models_executed=r.models_executed,
            credits_used=r.credits_used,
        )
        for r in rows
    ]


# ── dbt Cloud jobs cost breakdown ─────────────────────────────────────────────


@router.get("/dbt/jobs", response_model=list[DbtJobCostRecord])
async def get_dbt_jobs(
    request: Request,
    days: int = Query(30, ge=1, le=90),
) -> list[DbtJobCostRecord]:
    """Return credit and performance breakdown by dbt Cloud job."""
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar
    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with get_db() as session:
        result = await session.execute(select(DbtCloudRun).where(DbtCloudRun.started_at >= cutoff))
        runs = result.scalars().all()

    jobs: dict[int, dict] = {}
    for r in runs:
        jid = r.job_id
        if jid not in jobs:
            jobs[jid] = {
                "job_id": jid,
                "job_name": r.job_name,
                "environment_id": r.environment_id,
                "environment_name": r.environment_name,
                "project_id": r.project_id,
                "project_name": r.project_name,
                "run_count": 0,
                "total_credits": 0.0,
                "total_duration": 0.0,
                "duration_count": 0,
                "last_run_at": None,
                "last_run_status": None,
            }
        g = jobs[jid]
        g["run_count"] += 1
        g["total_credits"] += float(r.credits_used or 0)
        if r.duration_seconds is not None:
            g["total_duration"] += r.duration_seconds
            g["duration_count"] += 1
        if r.started_at and (g["last_run_at"] is None or r.started_at > g["last_run_at"]):
            g["last_run_at"] = r.started_at
            g["last_run_status"] = r.status

    result_list = [
        DbtJobCostRecord(
            job_id=g["job_id"],
            job_name=g["job_name"],
            environment_id=g["environment_id"],
            environment_name=g["environment_name"],
            project_id=g["project_id"],
            project_name=g["project_name"],
            run_count=g["run_count"],
            total_credits=round(g["total_credits"], 6),
            total_cost_usd=round(
                g["total_credits"] / credits_per_dollar if credits_per_dollar else 0, 4
            ),
            avg_duration_seconds=(
                round(g["total_duration"] / g["duration_count"], 1) if g["duration_count"] else None
            ),
            last_run_at=g["last_run_at"],
            last_run_status=g["last_run_status"],
        )
        for g in jobs.values()
    ]
    result_list.sort(key=lambda x: -x.total_credits)
    return result_list


# ── dbt Cloud environments cost breakdown ─────────────────────────────────────


@router.get("/dbt/environments", response_model=list[DbtEnvironmentCostRecord])
async def get_dbt_environments(
    request: Request,
    days: int = Query(30, ge=1, le=90),
) -> list[DbtEnvironmentCostRecord]:
    """Return credit breakdown by dbt Cloud environment."""
    config = request.app.state.config
    credits_per_dollar: float = config.credits_per_dollar
    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with get_db() as session:
        result = await session.execute(select(DbtCloudRun).where(DbtCloudRun.started_at >= cutoff))
        runs = result.scalars().all()

    envs: dict[int | None, dict] = {}
    for r in runs:
        eid = r.environment_id
        if eid not in envs:
            envs[eid] = {
                "environment_id": eid,
                "environment_name": r.environment_name,
                "project_id": r.project_id,
                "project_name": r.project_name,
                "run_count": 0,
                "total_credits": 0.0,
                "job_ids": set(),
            }
        g = envs[eid]
        g["run_count"] += 1
        g["total_credits"] += float(r.credits_used or 0)
        g["job_ids"].add(r.job_id)

    result_list = [
        DbtEnvironmentCostRecord(
            environment_id=g["environment_id"],
            environment_name=g["environment_name"],
            project_id=g["project_id"],
            project_name=g["project_name"],
            run_count=g["run_count"],
            total_credits=round(g["total_credits"], 6),
            total_cost_usd=round(
                g["total_credits"] / credits_per_dollar if credits_per_dollar else 0, 4
            ),
            distinct_jobs=len(g["job_ids"]),
        )
        for g in envs.values()
    ]
    result_list.sort(key=lambda x: -x.total_credits)
    return result_list


# ── Threshold alerts ──────────────────────────────────────────────────────────


@router.get("/dbt/threshold-alerts", response_model=list[DbtThresholdAlertRecord])
async def get_threshold_alerts(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
) -> list[DbtThresholdAlertRecord]:
    """Return dbt model threshold alerts, newest first."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    async with get_db() as session:
        result = await session.execute(
            select(DbtModelThresholdAlert)
            .where(DbtModelThresholdAlert.detected_at >= cutoff)
            .order_by(DbtModelThresholdAlert.detected_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

    return [
        DbtThresholdAlertRecord(
            id=r.id,
            detected_at=r.detected_at,
            dbt_model=r.dbt_model,
            period_start=r.period_start,
            period_end=r.period_end,
            credits_used=r.credits_used,
            threshold=r.threshold,
        )
        for r in rows
    ]


# ── Model metadata ────────────────────────────────────────────────────────────


@router.get("/dbt/metadata", response_model=list[DbtModelMetadataRecord])
async def get_dbt_metadata() -> list[DbtModelMetadataRecord]:
    """Return enriched dbt model metadata loaded from a manifest.json."""
    async with get_db() as session:
        result = await session.execute(
            select(DbtModelMetadata).order_by(DbtModelMetadata.model_name)
        )
        rows = result.scalars().all()

    return [
        DbtModelMetadataRecord(
            model_name=r.model_name,
            project_name=r.project_name,
            owner=r.owner,
            description=r.description,
            materialization=r.materialization,
            tags=json.loads(r.tags) if r.tags else [],
            schema_name=r.schema_name,
            database_name=r.database_name,
        )
        for r in rows
    ]


# ── dbt Cloud sync ────────────────────────────────────────────────────────────


@router.post("/dbt/sync-cloud", response_model=DbtCloudSyncResponse)
async def sync_dbt_cloud(request: Request) -> DbtCloudSyncResponse:
    """Pull the latest run + job + environment metadata from dbt Cloud.

    Requires ``dbt_cloud_account_id`` and ``dbt_cloud_api_token`` in config.
    """
    config = request.app.state.config
    account_id: str = getattr(config, "dbt_cloud_account_id", "")
    api_token_obj = getattr(config, "dbt_cloud_api_token", None)
    api_token: str = api_token_obj.get_secret_value() if api_token_obj else ""

    if not account_id or not api_token:
        raise HTTPException(
            status_code=503,
            detail=(
                "dbt Cloud not configured. "
                "Set dbt_cloud_account_id and dbt_cloud_api_token in config."
            ),
        )

    from frostwatch.dbt_cloud.client import DbtCloudClient

    client = DbtCloudClient(account_id=account_id, api_token=api_token)
    credits_per_dollar: float = config.credits_per_dollar

    try:
        import asyncio

        runs_raw, jobs_raw, envs_raw = await asyncio.gather(
            client.get_runs(days=30),
            client.get_jobs(),
            client.get_environments(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"dbt Cloud API error: {exc}") from exc

    job_map: dict[int, dict] = {j["job_id"]: j for j in jobs_raw if j.get("job_id")}
    env_map: dict[int, dict] = {e["environment_id"]: e for e in envs_raw if e.get("environment_id")}

    now = datetime.now(UTC)
    runs_synced = 0

    async with get_db() as session:
        for r in runs_raw:
            run_id = r.get("run_id")
            if not run_id:
                continue

            job = job_map.get(r.get("job_id") or 0, {})
            env = env_map.get(r.get("environment_id") or 0, {})

            credits = 0.0
            if r.get("started_at") and r.get("finished_at"):
                credits = await _attribute_credits(r["started_at"], r["finished_at"])

            stmt = sqlite_insert(DbtCloudRun).values(
                run_id=run_id,
                job_id=r.get("job_id"),
                job_name=job.get("job_name") or r.get("job_name"),
                environment_id=r.get("environment_id"),
                environment_name=env.get("environment_name"),
                project_id=r.get("project_id"),
                project_name=None,
                triggered_by=r.get("triggered_by"),
                status=r.get("status"),
                started_at=r.get("started_at"),
                finished_at=r.get("finished_at"),
                duration_seconds=r.get("duration_seconds"),
                models_executed=r.get("models_executed"),
                credits_used=round(credits / credits_per_dollar, 6) if credits_per_dollar else 0,
                synced_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["run_id"],
                set_={
                    "status": stmt.excluded.status,
                    "finished_at": stmt.excluded.finished_at,
                    "duration_seconds": stmt.excluded.duration_seconds,
                    "credits_used": stmt.excluded.credits_used,
                    "synced_at": stmt.excluded.synced_at,
                },
            )
            await session.execute(stmt)
            runs_synced += 1

    return DbtCloudSyncResponse(
        runs_synced=runs_synced,
        jobs_enriched=len(job_map),
        environments_enriched=len(env_map),
    )


async def _attribute_credits(started_at: datetime, finished_at: datetime) -> float:
    """Sum credits of dbt-tagged queries that ran inside a given time window."""
    async with get_db() as session:
        result = await session.execute(
            select(CachedQuery).where(
                CachedQuery.dbt_model.isnot(None),
                CachedQuery.start_time >= started_at,
                CachedQuery.start_time <= finished_at,
            )
        )
        rows = result.scalars().all()
    return sum(float(q.credits_used or 0) for q in rows)


# ── Manifest upload ───────────────────────────────────────────────────────────


@router.post("/dbt/manifest", response_model=dict)
async def upload_manifest(request: Request) -> dict:
    """Parse a dbt manifest.json submitted as the raw request body.

    Upserts enriched model metadata into the local database.
    Returns ``{"models_upserted": N}``.

    Example::

        curl -X POST http://localhost:8000/api/dbt/manifest \\
             -H "Content-Type: application/json" \\
             --data-binary @manifest.json
    """
    from frostwatch.dbt_cloud.manifest import parse_manifest

    try:
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Request body is empty")
        models = parse_manifest(body)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse manifest: {exc}") from exc

    if not models:
        return {"models_upserted": 0}

    now = datetime.now(UTC)
    async with get_db() as session:
        for m in models:
            stmt = sqlite_insert(DbtModelMetadata).values(
                model_name=m["model_name"],
                project_name=m["project_name"],
                owner=m["owner"],
                description=m["description"],
                materialization=m["materialization"],
                tags=m["tags"],
                schema_name=m["schema_name"],
                database_name=m["database_name"],
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["model_name"],
                set_={
                    "project_name": stmt.excluded.project_name,
                    "owner": stmt.excluded.owner,
                    "description": stmt.excluded.description,
                    "materialization": stmt.excluded.materialization,
                    "tags": stmt.excluded.tags,
                    "schema_name": stmt.excluded.schema_name,
                    "database_name": stmt.excluded.database_name,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await session.execute(stmt)

    return {"models_upserted": len(models)}
