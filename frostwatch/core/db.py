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
