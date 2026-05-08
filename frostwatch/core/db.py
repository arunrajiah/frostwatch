from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_engine = None
_session_factory = None


class Base(DeclarativeBase):
    pass


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    rows_synced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class CachedQuery(Base):
    __tablename__ = "cached_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_id: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    warehouse_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    schema_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    bytes_scanned: Mapped[float | None] = mapped_column(Float, nullable=True)
    partitions_scanned: Mapped[float | None] = mapped_column(Float, nullable=True)
    partitions_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    credits_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_tag: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dbt_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CachedWarehouseMetric(Base):
    __tablename__ = "cached_warehouse_metrics"
    __table_args__ = (UniqueConstraint("warehouse_name", "date", name="uq_wh_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_name: Mapped[str] = mapped_column(String(256), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    credits_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AnomalyRecord(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(128), nullable=False)
    warehouse_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SettingsStore(Base):
    __tablename__ = "settings_store"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class QueryRewrite(Base):
    __tablename__ = "query_rewrites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rewrite_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DbtCloudRun(Base):
    """Metadata for a dbt Cloud job run, synced from the dbt Cloud API."""

    __tablename__ = "dbt_cloud_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    job_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    environment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    environment_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    models_executed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DbtModelThresholdAlert(Base):
    """Fired when a dbt model exceeds its daily credit threshold."""

    __tablename__ = "dbt_model_threshold_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dbt_model: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    credits_used: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)


class DbtModelMetadata(Base):
    """Enriched model metadata parsed from a dbt manifest.json."""

    __tablename__ = "dbt_model_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    materialization: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    schema_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ResourceMonitor(Base):
    """Snowflake resource monitor definition, synced from ACCOUNT_USAGE."""

    __tablename__ = "resource_monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    credit_quota: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    remaining_credits: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ACCOUNT or WAREHOUSE
    frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)  # MONTHLY, DAILY, …
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notify_at_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    suspend_at_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    suspend_immediately_at_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    warehouses: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    owner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


async def init_db(db_path: Path) -> None:
    global _engine, _session_factory

    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(url, echo=False, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
        # Inline migrations for columns added after initial release
        for migration_sql in [
            "ALTER TABLE cached_queries ADD COLUMN dbt_model VARCHAR(256)",
            "ALTER TABLE cached_queries ADD COLUMN partitions_scanned FLOAT",
            "ALTER TABLE cached_queries ADD COLUMN partitions_total FLOAT",
        ]:
            with contextlib.suppress(Exception):
                await conn.execute(text(migration_sql))


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
