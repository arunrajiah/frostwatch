"""Seed the FrostWatch database with realistic synthetic data for demo mode.

Run via: frostwatch demo
"""
from __future__ import annotations

import json
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text

from frostwatch.core.config import FrostWatchConfig
from frostwatch.core.db import (
    AnomalyRecord,
    ReportRecord,
    SyncRun,
    get_db,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

WAREHOUSES = [
    ("COMPUTE_WH",      0.35),   # (name, base_credits_per_day)
    ("TRANSFORM_WH",    0.85),
    ("REPORTING_WH",    0.22),
    ("ML_WH",           0.60),
]

USERS = [
    "ANALYST_ALICE", "ENGINEER_BOB", "DATA_CARLOS",
    "SCIENTIST_DANA", "LOADER_SVC", "DBT_SVC",
]

ROLES = ["ANALYST", "TRANSFORMER", "REPORTER", "DATA_SCIENTIST", "SYSADMIN"]

DBT_MODELS = [
    "orders", "customers", "order_items", "products",
    "revenue_daily", "churn_features", "ltv_model",
    "marketing_attribution", "inventory_snapshot", "funnel_stages",
]

QUERY_TEMPLATES = [
    ("SELECT o.*, c.email FROM {db}.orders o JOIN {db}.customers c ON o.customer_id = c.id WHERE o.created_at >= DATEADD('day', -7, CURRENT_TIMESTAMP())", 0.004),
    ("SELECT warehouse_name, SUM(credits_used) credits FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY WHERE start_time >= DATEADD('month', -1, CURRENT_TIMESTAMP()) GROUP BY 1 ORDER BY 2 DESC", 0.001),
    ("CREATE OR REPLACE TABLE {db}.revenue_daily AS SELECT DATE_TRUNC('day', created_at) d, SUM(amount) revenue FROM {db}.orders GROUP BY 1", 0.012),
    ("SELECT user_id, COUNT(*) sessions, SUM(duration_sec) total_sec FROM {db}.sessions WHERE session_date BETWEEN '2026-01-01' AND CURRENT_DATE GROUP BY 1 HAVING sessions > 5", 0.008),
    ("MERGE INTO {db}.customers t USING {db}.customers_staging s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.email = s.email, t.updated_at = CURRENT_TIMESTAMP() WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.email, s.created_at, CURRENT_TIMESTAMP())", 0.020),
    ("SELECT p.sku, p.name, SUM(oi.qty) units_sold FROM {db}.products p JOIN {db}.order_items oi ON p.id = oi.product_id GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 100", 0.003),
    ("COPY INTO {db}.events_raw FROM @{db}.events_stage FILE_FORMAT = (TYPE = 'JSON') ON_ERROR = 'CONTINUE'", 0.006),
    ("SELECT DATE_TRUNC('week', event_ts) week, event_type, COUNT(*) n FROM {db}.events GROUP BY 1, 2", 0.005),
    ("WITH cohort AS (SELECT customer_id, MIN(DATE_TRUNC('month', created_at)) cohort_month FROM {db}.orders GROUP BY 1) SELECT c.cohort_month, DATE_TRUNC('month', o.created_at) order_month, COUNT(DISTINCT o.customer_id) retained FROM cohort c JOIN {db}.orders o USING (customer_id) GROUP BY 1, 2", 0.018),
    ("SELECT * FROM {db}.ml_features WHERE updated_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP()) ORDER BY score DESC LIMIT 10000", 0.030),
]

DB = "ANALYTICS"


def _dbt_tag(model: str) -> str:
    return json.dumps({
        "app": "dbt",
        "dbt_version": "1.8.2",
        "profile_name": "analytics",
        "target_name": "prod",
        "node_id": f"model.analytics.{model}",
    })


def _jitter(base: float, pct: float = 0.3) -> float:
    return max(0.0, base * (1 + random.uniform(-pct, pct)))


# ── Main seeder ───────────────────────────────────────────────────────────────

async def seed_demo(config: FrostWatchConfig, days: int = 35) -> None:
    """Populate the database with synthetic but realistic demo data."""
    rng = random.Random(42)   # deterministic — same data every time
    now = datetime.now(UTC)
    today = now.date()
    synced_at = now

    # ── Warehouse daily metrics (35 days × 4 warehouses) ──────────────────
    async with get_db() as session:
        for d_offset in range(days):
            day = today - timedelta(days=days - 1 - d_offset)
            for wh_name, base_credits in WAREHOUSES:
                # Inject a visible spike on day 8 for TRANSFORM_WH
                if wh_name == "TRANSFORM_WH" and d_offset == days - 8:
                    credits = _jitter(base_credits * 6.5, 0.1, )
                else:
                    credits = _jitter(base_credits, 0.35)
                # Weekend dip
                if date(day.year, day.month, day.day).weekday() >= 5:
                    credits *= 0.25
                credits = round(credits, 4)
                cost_usd = round(credits / config.credits_per_dollar, 4)

                await session.execute(
                    text(
                        "INSERT OR REPLACE INTO cached_warehouse_metrics "
                        "(warehouse_name, date, credits_used, cost_usd, synced_at) "
                        "VALUES (:wh, :d, :cr, :cu, :sa)"
                    ),
                    {"wh": wh_name, "d": day.isoformat(), "cr": credits, "cu": cost_usd, "sa": synced_at},
                )

    # ── Query history (last 30 days, ~500 rows) ────────────────────────────
    queries: list[dict] = []
    query_id_counter = 1000

    for d_offset in range(30):
        day_date = today - timedelta(days=29 - d_offset)
        # fewer queries on weekends
        n_queries = rng.randint(8, 25) if day_date.weekday() < 5 else rng.randint(1, 6)

        for _ in range(n_queries):
            hour = rng.randint(7, 22)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            start = datetime(day_date.year, day_date.month, day_date.day,
                             hour, minute, second, tzinfo=UTC)
            exec_ms = rng.lognormvariate(8.5, 1.2)   # realistic heavy-tail
            end = start + timedelta(milliseconds=exec_ms)

            wh_name, base_credits = rng.choice(WAREHOUSES)
            credits = max(0.0, rng.gauss(base_credits * 0.05, base_credits * 0.02))
            user = rng.choice(USERS)
            role = rng.choice(ROLES)
            tmpl, _ = rng.choice(QUERY_TEMPLATES)
            sql = tmpl.format(db=DB)
            bytes_scanned = rng.uniform(1e7, 5e10)

            # ~40 % of queries are dbt
            if user == "DBT_SVC" or rng.random() < 0.35:
                model = rng.choice(DBT_MODELS)
                tag = _dbt_tag(model)
                dbt_model: str | None = model
            else:
                tag = ""
                dbt_model = None

            queries.append({
                "query_id": f"demo-{query_id_counter:06d}",
                "warehouse_name": wh_name,
                "user_name": user,
                "role_name": role,
                "database_name": DB,
                "schema_name": "PUBLIC",
                "execution_time_ms": round(exec_ms, 2),
                "bytes_scanned": round(bytes_scanned, 0),
                "credits_used": round(credits, 8),
                "start_time": start,
                "end_time": end,
                "query_text": sql,
                "query_tag": tag,
                "dbt_model": dbt_model,
                "status": "SUCCESS",
                "synced_at": synced_at,
            })
            query_id_counter += 1

    async with get_db() as session:
        for q in queries:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO cached_queries "
                    "(query_id, warehouse_name, user_name, role_name, database_name, "
                    "schema_name, execution_time_ms, bytes_scanned, credits_used, "
                    "start_time, end_time, query_text, query_tag, dbt_model, status, synced_at) "
                    "VALUES (:query_id, :warehouse_name, :user_name, :role_name, :database_name, "
                    ":schema_name, :execution_time_ms, :bytes_scanned, :credits_used, "
                    ":start_time, :end_time, :query_text, :query_tag, :dbt_model, :status, :synced_at)"
                ),
                q,
            )

    # ── Anomalies (2 pre-baked) ────────────────────────────────────────────
    anomaly_time = now - timedelta(days=7)
    async with get_db() as session:
        session.add(AnomalyRecord(
            detected_at=anomaly_time,
            anomaly_type="spend_spike",
            warehouse_name="TRANSFORM_WH",
            severity="high",
            description=(
                "TRANSFORM_WH spent 6.5× its 21-day rolling average on "
                f"{(today - timedelta(days=8)).isoformat()}. "
                "Total credits: 5.53 vs baseline 0.85."
            ),
            llm_explanation=(
                "A significant spend spike was detected on TRANSFORM_WH. "
                "The warehouse consumed 6.5× its normal daily credits, likely caused by "
                "a large unoptimized merge or full table scan that ran without a result cache hit. "
                "Check the top queries for that day — look for full-table scans or cartesian joins "
                "and consider adding clustering keys or query filters."
            ),
        ))
        session.add(AnomalyRecord(
            detected_at=now - timedelta(days=2),
            anomaly_type="spend_spike",
            warehouse_name="ML_WH",
            severity="medium",
            description=(
                "ML_WH spent 3.2× its 21-day rolling average two days ago. "
                "Likely caused by a hyperparameter sweep or feature backfill."
            ),
            llm_explanation=(
                "ML_WH experienced a medium-severity spend spike, consuming 3.2× its rolling baseline. "
                "This pattern is consistent with a batch ML training job or a large feature backfill "
                "running outside normal hours. Consider scheduling intensive ML workloads during "
                "off-peak windows or using auto-suspend to limit runaway costs."
            ),
        ))

    # ── Sync run record ────────────────────────────────────────────────────
    async with get_db() as session:
        session.add(SyncRun(
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
            status="success",
            rows_synced=len(queries) + days * len(WAREHOUSES),
        ))

    # ── Report ────────────────────────────────────────────────────────────
    period_end = now
    period_start = now - timedelta(days=7)
    async with get_db() as session:
        session.add(ReportRecord(
            generated_at=now - timedelta(hours=3),
            period_start=period_start,
            period_end=period_end,
            summary_text=(
                "Weekly digest for the period ending "
                f"{period_end.strftime('%b %d, %Y')}:\n\n"
                "Total spend this week: $14.82 across 4 warehouses.\n"
                "TRANSFORM_WH is your most expensive warehouse (58% of total spend).\n"
                "dbt models consumed 42% of all Snowflake credits this week.\n"
                "Top dbt model by cost: `revenue_daily` (0.31 credits).\n"
                "2 anomalies were detected — see the Anomalies page for details."
            ),
            details_json=json.dumps({
                "warehouses": [
                    {"name": wh, "credits": round(_jitter(base * 7, 0.15), 3)}
                    for wh, base in WAREHOUSES
                ],
                "top_dbt_models": [
                    {"model": m, "credits": round(rng.uniform(0.05, 0.35), 4)}
                    for m in DBT_MODELS[:5]
                ],
            }),
        ))
