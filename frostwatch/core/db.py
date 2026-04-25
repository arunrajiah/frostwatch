from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_engine = None
_session_factory = None


class Base(DeclarativeBase):
    pass


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")
    rows_synced = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


class CachedQuery(Base):
    __tablename__ = "cached_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(256), unique=True, nullable=False)
    warehouse_name = Column(String(256), nullable=True)
    user_name = Column(String(256), nullable=True)
    role_name = Column(String(256), nullable=True)
    database_name = Column(String(256), nullable=True)
    schema_name = Column(String(256), nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    bytes_scanned = Column(Float, nullable=True)
    credits_used = Column(Float, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    query_text = Column(Text, nullable=True)
    query_tag = Column(String(512), nullable=True)
    status = Column(String(64), nullable=True)
    synced_at = Column(DateTime, nullable=False)


class CachedWarehouseMetric(Base):
    __tablename__ = "cached_warehouse_metrics"
    __table_args__ = (UniqueConstraint("warehouse_name", "date", name="uq_wh_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_name = Column(String(256), nullable=False)
    date = Column(Date, nullable=False)
    credits_used = Column(Float, nullable=False, default=0.0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    synced_at = Column(DateTime, nullable=False)


class AnomalyRecord(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, nullable=False)
    anomaly_type = Column(String(128), nullable=False)
    warehouse_name = Column(String(256), nullable=True)
    severity = Column(String(20), nullable=False, default="medium")
    description = Column(Text, nullable=True)
    llm_explanation = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class ReportRecord(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, nullable=False)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    summary_text = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)


class SettingsStore(Base):
    __tablename__ = "settings_store"

    key = Column(String(256), primary_key=True)
    value = Column(Text, nullable=False)


async def init_db(db_path: Path) -> None:
    global _engine, _session_factory

    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(url, echo=False, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)


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
