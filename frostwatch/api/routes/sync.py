from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from frostwatch.analysis.anomaly import detect_anomalies
from frostwatch.api.limiter import limiter
from frostwatch.api.models import SyncStatus
from frostwatch.core.db import (
    AnomalyRecord,
    CachedQuery,
    CachedWarehouseMetric,
    DbtModelThresholdAlert,
    ResourceMonitor,
    SyncRun,
    get_db,
)
from frostwatch.snowflake.queries import (
    QUERY_HISTORY_SQL,
    RESOURCE_MONITORS_SQL,
    WAREHOUSE_METERING_SQL,
)

router = APIRouter()

_sync_running: bool = False


async def run_sync(config, snowflake_client, llm_provider=None) -> None:
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
        query_limit = getattr(config, "snowflake_query_limit", 500)
        query_rows = await snowflake_client.execute(
            QUERY_HISTORY_SQL, {"days": 30, "limit": query_limit}
        )
        metric_rows = await snowflake_client.execute(WAREHOUSE_METERING_SQL, {"days": 30})
        try:
            monitor_rows = await snowflake_client.execute(RESOURCE_MONITORS_SQL, {})
        except Exception:
            monitor_rows = []  # not all accounts have resource monitors; skip gracefully

        synced_at = datetime.now(UTC)
        rows_synced = 0

        async with get_db() as session:
            for row in query_rows:
                raw_tag = str(row.get("QUERY_TAG") or row.get("query_tag") or "")
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
                    partitions_scanned=_to_float(
                        row.get("PARTITIONS_SCANNED") or row.get("partitions_scanned")
                    ),
                    partitions_total=_to_float(
                        row.get("PARTITIONS_TOTAL") or row.get("partitions_total")
                    ),
                    credits_used=_to_float(row.get("CREDITS_USED") or row.get("credits_used")),
                    start_time=row.get("START_TIME") or row.get("start_time"),
                    end_time=row.get("END_TIME") or row.get("end_time"),
                    query_text=str(row.get("QUERY_TEXT") or row.get("query_text") or ""),
                    query_tag=raw_tag,
                    dbt_model=_extract_dbt_model(raw_tag),
                    status=str(row.get("STATUS") or row.get("status") or ""),
                    synced_at=synced_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["query_id"],
                    set_={
                        "credits_used": stmt.excluded.credits_used,
                        "execution_time_ms": stmt.excluded.execution_time_ms,
                        "bytes_scanned": stmt.excluded.bytes_scanned,
                        "partitions_scanned": stmt.excluded.partitions_scanned,
                        "partitions_total": stmt.excluded.partitions_total,
                        "dbt_model": stmt.excluded.dbt_model,
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

        # ── Resource monitors ──────────────────────────────────────────────
        if monitor_rows:
            async with get_db() as session:
                for row in monitor_rows:
                    name = str(row.get("NAME") or row.get("name") or "")
                    if not name:
                        continue
                    wh_raw = row.get("WAREHOUSES") or row.get("warehouses") or ""
                    wh_list = [w.strip() for w in str(wh_raw).split(",") if w.strip()]
                    stmt = sqlite_insert(ResourceMonitor).values(
                        name=name,
                        credit_quota=_to_float(row.get("CREDIT_QUOTA") or row.get("credit_quota")),
                        used_credits=_to_float(row.get("USED_CREDITS") or row.get("used_credits")),
                        remaining_credits=_to_float(
                            row.get("REMAINING_CREDITS") or row.get("remaining_credits")
                        ),
                        level=str(row.get("LEVEL") or row.get("level") or ""),
                        frequency=str(row.get("FREQUENCY") or row.get("frequency") or ""),
                        start_time=row.get("START_TIME") or row.get("start_time"),
                        end_time=row.get("END_TIME") or row.get("end_time"),
                        notify_at_percentage=_to_float(
                            row.get("NOTIFY_AT_PERCENTAGE") or row.get("notify_at_percentage")
                        ),
                        suspend_at_percentage=_to_float(
                            row.get("SUSPEND_AT_PERCENTAGE") or row.get("suspend_at_percentage")
                        ),
                        suspend_immediately_at_percentage=_to_float(
                            row.get("SUSPEND_IMMEDIATELY_AT_PERCENTAGE")
                            or row.get("suspend_immediately_at_percentage")
                        ),
                        warehouses=json.dumps(wh_list),
                        owner=str(row.get("OWNER") or row.get("owner") or ""),
                        created_on=row.get("CREATED_ON") or row.get("created_on"),
                        synced_at=synced_at,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["name"],
                        set_={
                            "credit_quota": stmt.excluded.credit_quota,
                            "used_credits": stmt.excluded.used_credits,
                            "remaining_credits": stmt.excluded.remaining_credits,
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
                    llm_explanation: str | None = None
                    if llm_provider is not None:
                        try:
                            prompt = (
                                f"Anomaly detected: {a.anomaly_type}\n"
                                f"Warehouse: {a.warehouse_name}\n"
                                f"Severity: {a.severity}\n"
                                f"Details: {a.description}\n\n"
                                "In 2-3 sentences, explain what this anomaly means and suggest a remedy."
                            )
                            llm_explanation = await llm_provider.complete(
                                prompt, system="You are a Snowflake cost optimization expert."
                            )
                        except Exception:
                            pass
                    record = AnomalyRecord(
                        detected_at=detection_time,
                        anomaly_type=a.anomaly_type,
                        warehouse_name=a.warehouse_name,
                        severity=a.severity,
                        description=a.description,
                        llm_explanation=llm_explanation,
                    )
                    session.add(record)

        # ── dbt model threshold alerts ─────────────────────────────────────
        threshold = getattr(config, "dbt_model_credit_threshold", 0.0)
        if threshold and threshold > 0:
            await _check_dbt_thresholds(threshold, detection_time)

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


async def _check_dbt_thresholds(threshold: float, now: datetime) -> None:
    """Fire threshold alerts for any dbt model that exceeded *threshold* credits today."""
    from collections import defaultdict

    period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = now

    async with get_db() as session:
        result = await session.execute(
            select(CachedQuery).where(
                CachedQuery.dbt_model.isnot(None),
                CachedQuery.start_time >= period_start,
                CachedQuery.start_time <= period_end,
            )
        )
        rows = result.scalars().all()

    model_credits: dict[str, float] = defaultdict(float)
    for q in rows:
        model_credits[q.dbt_model or ""] += float(q.credits_used or 0)

    alerts = [
        DbtModelThresholdAlert(
            detected_at=now,
            dbt_model=model,
            period_start=period_start,
            period_end=period_end,
            credits_used=round(credits, 6),
            threshold=threshold,
        )
        for model, credits in model_credits.items()
        if credits > threshold
    ]

    if alerts:
        async with get_db() as session:
            for alert in alerts:
                session.add(alert)


def _extract_dbt_model(query_tag: str | None) -> str | None:
    """Parse dbt model name from Snowflake query_tag JSON.

    dbt sets query_tag to JSON such as:
      {"app": "dbt", "node_id": "model.project.model_name", ...}
    or nested:
      {"dbt_snowflake_query_tags": {"app": "dbt", "node_id": "model.project.model_name"}}
    """
    if not query_tag:
        return None
    try:
        tag = json.loads(query_tag)
        if not isinstance(tag, dict):
            return None
        # Unwrap nested dbt_snowflake_query_tags format
        if "dbt_snowflake_query_tags" in tag:
            tag = tag["dbt_snowflake_query_tags"]
        app = tag.get("app", "")
        if not isinstance(app, str) or not app.lower().startswith("dbt"):
            return None
        node_id = tag.get("node_id", "")
        if isinstance(node_id, str) and node_id.startswith("model."):
            return node_id.rsplit(".", 1)[-1]
        return None
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@router.post("/sync")
@limiter.limit("10/minute")
async def start_sync(request: Request, background_tasks: BackgroundTasks) -> dict:
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    from frostwatch.snowflake.client import SnowflakeClient

    config = request.app.state.config
    client = SnowflakeClient(config)
    llm = request.app.state.llm_provider
    background_tasks.add_task(run_sync, config, client, llm)
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
