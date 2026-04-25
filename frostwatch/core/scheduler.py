from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig


def _parse_cron(cron_expr: str) -> CronTrigger:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr!r}. Expected 5 fields.")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )


def create_scheduler(config: "FrostWatchConfig", app_state: Any) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def sync_job() -> None:
        from frostwatch.snowflake.client import SnowflakeClient
        from frostwatch.api.routes.sync import run_sync

        client = SnowflakeClient(app_state.config)
        await run_sync(app_state.config, client)

    async def report_job() -> None:
        from frostwatch.api.routes.sync import run_sync
        from frostwatch.snowflake.client import SnowflakeClient
        from frostwatch.analysis.cost import compute_cost_breakdown
        from frostwatch.analysis.anomaly import detect_anomalies
        from frostwatch.analysis.recommendations import generate_report
        from frostwatch.alerts.slack import send_slack_digest
        from frostwatch.alerts.email import send_email_digest
        from frostwatch.core.db import get_db, CachedQuery, CachedWarehouseMetric
        from sqlalchemy import select
        from datetime import datetime, timedelta, timezone

        current_config = app_state.config
        client = SnowflakeClient(current_config)
        await run_sync(current_config, client)

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        async with get_db() as session:
            q_result = await session.execute(
                select(CachedQuery).where(CachedQuery.start_time >= cutoff)
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
            queries, warehouse_metrics, current_config.credits_per_dollar
        )
        anomalies = detect_anomalies(warehouse_metrics, current_config)

        llm = app_state.llm_provider
        report_text = await generate_report(
            llm, queries, [a.model_dump() for a in anomalies], cost_breakdown, period_days=7
        )

        cost_summary = {
            "total_credits_7d": cost_breakdown.total_credits,
            "total_cost_usd_7d": cost_breakdown.total_cost_usd,
        }

        if current_config.slack_webhook_url:
            await send_slack_digest(
                current_config.slack_webhook_url, report_text, cost_summary
            )

        if current_config.email_smtp_host and current_config.email_recipients:
            await send_email_digest(current_config, report_text, cost_summary)

    try:
        cron_trigger = _parse_cron(config.schedule_cron)
    except ValueError:
        cron_trigger = CronTrigger(day_of_week="mon", hour=8, minute=0)

    scheduler.add_job(
        sync_job,
        trigger=CronTrigger(hour="*/6"),
        id="sync_job",
        name="Snowflake Data Sync",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        report_job,
        trigger=cron_trigger,
        id="report_job",
        name="Weekly Report & Alerts",
        replace_existing=True,
        misfire_grace_time=600,
    )

    return scheduler


def get_jobs_info(scheduler: AsyncIOScheduler) -> list[dict]:
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append(
            {
                "job_id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
                "trigger_description": str(job.trigger),
            }
        )
    return jobs
