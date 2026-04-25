from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from frostwatch.analysis.anomaly import detect_anomalies
from frostwatch.api.models import SyncStatus
from frostwatch.core.db import (
    AnomalyRecord,
    CachedQuery,
    CachedWarehouseMetric,
    SyncRun,
    get_db,
)
from frostwatch.snowflake.queries import QUERY_HISTORY_SQL, WAREHOUSE_METERING_SQL

router = APIRouter()

_sync_running: bool = False


async def run_sync(config, snowflake_client) -> None:
    global _sync_running
    _sync_running = True

    now = datetime.now(UTC)
    sync_run_id: int | None = None

    async with get_db() as session:
        run = SyncRun(started_at=now, status="running")
        session.add(run)
        await session.flush()
        sync_run_id = run.id

    try:
        query_rows = await snowflake_client.execute(QUERY_HISTORY_SQL, {"days": 30})
        metric_rows = await snowflake_client.execute(WAREHOUSE_METERING_SQL, {"days": 30})

        synced_at = datetime.now(UTC)
        rows_synced = 0

        async with get_db() as session:
            for row in query_rows:
                stmt = sqlite_insert(CachedQuery).values(
                    query_id=str(row.get("QUERY_ID") or row.get("query_id", "")),
                    warehouse_name=row.get("WAREHOUSE_NAME") or row.get("warehouse_name"),
                    user_name=row.get("USER_NAME") or row.get("user_name"),
                    role_name=row.get("ROLE_NAME") or row.get("role_name"),
                    database_name=row.get("DATABASE_NAME") or row.get("database_name"),
                    schema_name=row.get("SCHEMA_NAME") or row.get("schema_name"),
                    execution_time_ms=_to_float(
                        row.get("EXECUTION_TIME_MS") or row.get("execution_time_ms")
                    ),
                    bytes_scanned=_to_float(row.get("BYTES_SCANNED") or row.get("bytes_scanned")),
                    credits_used=_to_float(row.get("CREDITS_USED") or row.get("credits_used")),
                    start_time=row.get("START_TIME") or row.get("start_time"),
                    end_time=row.get("END_TIME") or row.get("end_time"),
                    query_text=str(row.get("QUERY_TEXT") or row.get("query_text") or ""),
                    query_tag=str(row.get("QUERY_TAG") or row.get("query_tag") or ""),
                    status=str(row.get("STATUS") or row.get("status") or ""),
                    synced_at=synced_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["query_id"],
                    set_={
                        "credits_used": stmt.excluded.credits_used,
                        "execution_time_ms": stmt.excluded.execution_time_ms,
                        "bytes_scanned": stmt.excluded.bytes_scanned,
                        "synced_at": stmt.excluded.synced_at,
                    },
                )
                await session.execute(stmt)
                rows_synced += 1

        async with get_db() as session:
            for row in metric_rows:
                wh_name = str(row.get("WAREHOUSE_NAME") or row.get("warehouse_name") or "")
                usage_date = row.get("USAGE_DATE") or row.get("usage_date")
                credits = _to_float(row.get("CREDITS_USED") or row.get("credits_used")) or 0.0
                cost_usd = credits / config.credits_per_dollar if config.credits_per_dollar else 0.0

                if not wh_name or usage_date is None:
                    continue

                if hasattr(usage_date, "date"):
                    usage_date = usage_date.date()

                stmt = sqlite_insert(CachedWarehouseMetric).values(
                    warehouse_name=wh_name,
                    date=usage_date,
                    credits_used=credits,
                    cost_usd=cost_usd,
                    synced_at=synced_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["warehouse_name", "date"],
                    set_={
                        "credits_used": stmt.excluded.credits_used,
                        "cost_usd": stmt.excluded.cost_usd,
                        "synced_at": stmt.excluded.synced_at,
                    },
                )
                await session.execute(stmt)
                rows_synced += 1

        async with get_db() as session:
            wm_result = await session.execute(select(CachedWarehouseMetric))
            all_metrics = [
                {c.name: getattr(row, c.name) for c in CachedWarehouseMetric.__table__.columns}
                for row in wm_result.scalars().all()
            ]

        anomalies = detect_anomalies(all_metrics, config)
        detection_time = datetime.now(UTC)

        if anomalies:
            async with get_db() as session:
                for a in anomalies:
                    record = AnomalyRecord(
                        detected_at=detection_time,
                        anomaly_type=a.anomaly_type,
                        warehouse_name=a.warehouse_name,
                        severity=a.severity,
                        description=a.description,
                    )
                    session.add(record)

        async with get_db() as session:
            result = await session.execute(select(SyncRun).where(SyncRun.id == sync_run_id))
            run = result.scalar_one()
            run.status = "success"
            run.finished_at = datetime.now(UTC)
            run.rows_synced = rows_synced

    except Exception as exc:
        if sync_run_id:
            async with get_db() as session:
                result = await session.execute(select(SyncRun).where(SyncRun.id == sync_run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = "error"
                    run.finished_at = datetime.now(UTC)
                    run.error_message = str(exc)
        raise
    finally:
        _sync_running = False


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@router.post("/sync")
async def start_sync(request: Request, background_tasks: BackgroundTasks) -> dict:
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    from frostwatch.snowflake.client import SnowflakeClient

    config = request.app.state.config
    client = SnowflakeClient(config)
    background_tasks.add_task(run_sync, config, client)
    return {"status": "started"}


@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status() -> SyncStatus:
    global _sync_running

    try:
        async with get_db() as session:
            result = await session.execute(
                select(SyncRun).order_by(desc(SyncRun.started_at)).limit(1)
            )
            last_run = result.scalar_one_or_none()

        if last_run is None:
            return SyncStatus(
                status="idle",
                last_run_at=None,
                last_error=None,
                rows_synced=None,
            )

        if _sync_running:
            status = "running"
        elif last_run.status == "error":
            status = "error"
        else:
            status = "idle"

        return SyncStatus(
            status=status,
            last_run_at=last_run.finished_at or last_run.started_at,
            last_error=last_run.error_message if last_run.status == "error" else None,
            rows_synced=last_run.rows_synced,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
