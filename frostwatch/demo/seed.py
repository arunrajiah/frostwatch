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
    DbtCloudRun,
    DbtModelMetadata,
    DbtModelThresholdAlert,
    QueryRewrite,
    ReportRecord,
    ResourceMonitor,
    SyncRun,
    get_db,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

WAREHOUSES = [
    ("COMPUTE_WH", 0.35),  # (name, base_credits_per_day)
    ("TRANSFORM_WH", 0.85),
    ("REPORTING_WH", 0.22),
    ("ML_WH", 0.60),
]

USERS = [
    "ANALYST_ALICE",
    "ENGINEER_BOB",
    "DATA_CARLOS",
    "SCIENTIST_DANA",
    "LOADER_SVC",
    "DBT_SVC",
]

ROLES = ["ANALYST", "TRANSFORMER", "REPORTER", "DATA_SCIENTIST", "SYSADMIN"]

DBT_MODELS = [
    "orders",
    "customers",
    "order_items",
    "products",
    "revenue_daily",
    "churn_features",
    "ltv_model",
    "marketing_attribution",
    "inventory_snapshot",
    "funnel_stages",
]

QUERY_TEMPLATES = [
    (
        "SELECT o.*, c.email FROM {db}.orders o JOIN {db}.customers c ON o.customer_id = c.id WHERE o.created_at >= DATEADD('day', -7, CURRENT_TIMESTAMP())",
        0.004,
    ),
    (
        "SELECT warehouse_name, SUM(credits_used) credits FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY WHERE start_time >= DATEADD('month', -1, CURRENT_TIMESTAMP()) GROUP BY 1 ORDER BY 2 DESC",
        0.001,
    ),
    (
        "CREATE OR REPLACE TABLE {db}.revenue_daily AS SELECT DATE_TRUNC('day', created_at) d, SUM(amount) revenue FROM {db}.orders GROUP BY 1",
        0.012,
    ),
    (
        "SELECT user_id, COUNT(*) sessions, SUM(duration_sec) total_sec FROM {db}.sessions WHERE session_date BETWEEN '2026-01-01' AND CURRENT_DATE GROUP BY 1 HAVING sessions > 5",
        0.008,
    ),
    (
        "MERGE INTO {db}.customers t USING {db}.customers_staging s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.email = s.email, t.updated_at = CURRENT_TIMESTAMP() WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.email, s.created_at, CURRENT_TIMESTAMP())",
        0.020,
    ),
    (
        "SELECT p.sku, p.name, SUM(oi.qty) units_sold FROM {db}.products p JOIN {db}.order_items oi ON p.id = oi.product_id GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 100",
        0.003,
    ),
    (
        "COPY INTO {db}.events_raw FROM @{db}.events_stage FILE_FORMAT = (TYPE = 'JSON') ON_ERROR = 'CONTINUE'",
        0.006,
    ),
    (
        "SELECT DATE_TRUNC('week', event_ts) week, event_type, COUNT(*) n FROM {db}.events GROUP BY 1, 2",
        0.005,
    ),
    (
        "WITH cohort AS (SELECT customer_id, MIN(DATE_TRUNC('month', created_at)) cohort_month FROM {db}.orders GROUP BY 1) SELECT c.cohort_month, DATE_TRUNC('month', o.created_at) order_month, COUNT(DISTINCT o.customer_id) retained FROM cohort c JOIN {db}.orders o USING (customer_id) GROUP BY 1, 2",
        0.018,
    ),
    (
        "SELECT * FROM {db}.ml_features WHERE updated_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP()) ORDER BY score DESC LIMIT 10000",
        0.030,
    ),
]

DB = "ANALYTICS"


def _dbt_tag(model: str) -> str:
    return json.dumps(
        {
            "app": "dbt",
            "dbt_version": "1.8.2",
            "profile_name": "analytics",
            "target_name": "prod",
            "node_id": f"model.analytics.{model}",
        }
    )


def _jitter(base: float, pct: float = 0.3) -> float:
    return max(0.0, base * (1 + random.uniform(-pct, pct)))


# ── Main seeder ───────────────────────────────────────────────────────────────


async def seed_demo(config: FrostWatchConfig, days: int = 35) -> None:
    """Populate the database with synthetic but realistic demo data."""
    rng = random.Random(42)  # deterministic — same data every time
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
                    credits = _jitter(
                        base_credits * 6.5,
                        0.1,
                    )
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
                    {
                        "wh": wh_name,
                        "d": day.isoformat(),
                        "cr": credits,
                        "cu": cost_usd,
                        "sa": synced_at,
                    },
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
            start = datetime(
                day_date.year, day_date.month, day_date.day, hour, minute, second, tzinfo=UTC
            )
            exec_ms = rng.lognormvariate(8.5, 1.2)  # realistic heavy-tail
            end = start + timedelta(milliseconds=exec_ms)

            wh_name, base_credits = rng.choice(WAREHOUSES)
            credits = max(0.0, rng.gauss(base_credits * 0.05, base_credits * 0.02))
            user = rng.choice(USERS)
            role = rng.choice(ROLES)
            tmpl, _ = rng.choice(QUERY_TEMPLATES)
            sql = tmpl.format(db=DB)
            bytes_scanned = rng.uniform(1e7, 5e10)

            # Partition stats — total partitions drawn from table size proxy;
            # most queries have decent pruning, but ~25% are poor (ratio > 0.6)
            partitions_total = int(rng.uniform(200, 8000))
            if rng.random() < 0.25:
                # Poor pruning: scan 65–100% of partitions
                pruning_ratio = rng.uniform(0.65, 1.0)
            else:
                # Good pruning: scan 5–45% of partitions
                pruning_ratio = rng.uniform(0.05, 0.45)
            partitions_scanned = max(1, int(partitions_total * pruning_ratio))

            # ~40 % of queries are dbt
            if user == "DBT_SVC" or rng.random() < 0.35:
                model = rng.choice(DBT_MODELS)
                tag = _dbt_tag(model)
                dbt_model: str | None = model
            else:
                tag = ""
                dbt_model = None

            queries.append(
                {
                    "query_id": f"demo-{query_id_counter:06d}",
                    "warehouse_name": wh_name,
                    "user_name": user,
                    "role_name": role,
                    "database_name": DB,
                    "schema_name": "PUBLIC",
                    "execution_time_ms": round(exec_ms, 2),
                    "bytes_scanned": round(bytes_scanned, 0),
                    "partitions_scanned": partitions_scanned,
                    "partitions_total": partitions_total,
                    "credits_used": round(credits, 8),
                    "start_time": start,
                    "end_time": end,
                    "query_text": sql,
                    "query_tag": tag,
                    "dbt_model": dbt_model,
                    "status": "SUCCESS",
                    "synced_at": synced_at,
                }
            )
            query_id_counter += 1

    async with get_db() as session:
        for q in queries:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO cached_queries "
                    "(query_id, warehouse_name, user_name, role_name, database_name, "
                    "schema_name, execution_time_ms, bytes_scanned, partitions_scanned, "
                    "partitions_total, credits_used, "
                    "start_time, end_time, query_text, query_tag, dbt_model, status, synced_at) "
                    "VALUES (:query_id, :warehouse_name, :user_name, :role_name, :database_name, "
                    ":schema_name, :execution_time_ms, :bytes_scanned, :partitions_scanned, "
                    ":partitions_total, :credits_used, "
                    ":start_time, :end_time, :query_text, :query_tag, :dbt_model, :status, :synced_at)"
                ),
                q,
            )

    # ── Anomalies (2 pre-baked) ────────────────────────────────────────────
    anomaly_time = now - timedelta(days=7)
    async with get_db() as session:
        session.add(
            AnomalyRecord(
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
            )
        )
        session.add(
            AnomalyRecord(
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
            )
        )

    # ── Sync run record ────────────────────────────────────────────────────
    async with get_db() as session:
        session.add(
            SyncRun(
                started_at=now - timedelta(minutes=2),
                finished_at=now - timedelta(minutes=1),
                status="success",
                rows_synced=len(queries) + days * len(WAREHOUSES),
            )
        )

    # ── Pre-baked AI rewrites ─────────────────────────────────────────────────
    if queries:
        from frostwatch.analysis.fingerprint import fingerprint_sql

        sorted_queries = sorted(queries, key=lambda x: x["credits_used"], reverse=True)
        ml_query = next((q for q in sorted_queries if "ml_features" in q["query_text"]), None)
        merge_query = next((q for q in sorted_queries if "MERGE INTO" in q["query_text"]), None)

        async with get_db() as session:
            if ml_query:
                session.add(
                    QueryRewrite(
                        query_id=ml_query["query_id"],
                        fingerprint=fingerprint_sql(ml_query["query_text"]),
                        generated_at=now - timedelta(hours=1),
                        rewrite_suggestion=(
                            "## Rewrite\n\n"
                            "```sql\n"
                            "-- Specify only the columns you need instead of SELECT *\n"
                            "-- and add a selectivity filter before the ORDER BY.\n"
                            "SELECT user_id, score, feature_a, feature_b, updated_at\n"
                            "FROM ANALYTICS.ml_features\n"
                            "WHERE updated_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP())\n"
                            "  AND score > 0.5   -- push high-selectivity filter first\n"
                            "ORDER BY score DESC\n"
                            "LIMIT 10000;\n"
                            "```\n\n"
                            "## Root Cause\n\n"
                            "`SELECT *` forces Snowflake to read every column (typically 30-50) "
                            "even though only a handful are consumed downstream. The recency filter "
                            "on `updated_at` is applied after the full micro-partition scan rather "
                            "than being pruned early.\n\n"
                            "## Recommendations\n\n"
                            "- Replace `SELECT *` with explicit columns — reduces bytes scanned "
                            "by 60-80%.\n"
                            "- Add a **clustering key on `updated_at`** so Snowflake prunes "
                            "micro-partitions automatically.\n"
                            "- Consider a **materialized view** for the top-N rows by score if "
                            "this runs on a fixed cadence.\n"
                            "- This query is I/O-bound; downsize the warehouse to X-Small "
                            "for sub-1 GB result sets.\n\n"
                            "## Estimated Savings\n\n"
                            "Explicit columns + clustering key: **55–70%** fewer credits per run."
                        ),
                    )
                )
            if merge_query:
                session.add(
                    QueryRewrite(
                        query_id=merge_query["query_id"],
                        fingerprint=fingerprint_sql(merge_query["query_text"]),
                        generated_at=now - timedelta(hours=2),
                        rewrite_suggestion=(
                            "## Rewrite\n\n"
                            "```sql\n"
                            "-- Filter staging to only rows modified since last sync\n"
                            "MERGE INTO ANALYTICS.customers t\n"
                            "USING (\n"
                            "    SELECT id, email, created_at\n"
                            "    FROM ANALYTICS.customers_staging\n"
                            "    WHERE updated_at >= DATEADD('hour', -6, CURRENT_TIMESTAMP())\n"
                            ") s\n"
                            "ON t.id = s.id\n"
                            "WHEN MATCHED AND t.email <> s.email\n"
                            "    THEN UPDATE SET t.email = s.email,\n"
                            "                   t.updated_at = CURRENT_TIMESTAMP()\n"
                            "WHEN NOT MATCHED\n"
                            "    THEN INSERT (id, email, created_at, updated_at)\n"
                            "         VALUES (s.id, s.email, s.created_at, CURRENT_TIMESTAMP());\n"
                            "```\n\n"
                            "## Root Cause\n\n"
                            "The MERGE reads the entire `customers_staging` table every run. "
                            "For incremental loads this is unnecessary — most rows haven't changed. "
                            "The MATCHED branch also re-updates rows even when `email` is identical, "
                            "generating unnecessary write I/O.\n\n"
                            "## Recommendations\n\n"
                            "- **Filter staging to incremental rows** using an `updated_at` "
                            "predicate — reduces the join dataset by 90%+.\n"
                            "- Add `AND t.email <> s.email` to skip no-op updates.\n"
                            "- **Cluster `customers` on `id`** for faster join pruning.\n"
                            "- Use a large warehouse only for the initial backfill; subsequent "
                            "incremental MERGEs run fine on X-Small.\n\n"
                            "## Estimated Savings\n\n"
                            "Incremental filter + no-op guard: **70–85%** fewer credits per run."
                        ),
                    )
                )

    # ── dbt Cloud runs (30 days, 3 jobs, 2 environments) ─────────────────
    dbt_jobs = [
        (101, "Nightly Production Run", 201, "production"),
        (102, "Hourly Staging Refresh", 202, "staging"),
        (103, "Weekly Full Refresh", 201, "production"),
    ]
    dbt_run_id = 5000
    async with get_db() as session:
        for d_offset in range(30):
            run_date = today - timedelta(days=29 - d_offset)
            is_weekend = run_date.weekday() >= 5
            # Nightly runs every day; hourly ~3/day on weekdays; weekly on Mondays
            run_schedule = [
                (101, 1),  # nightly — 1 run/day
                (102, 0 if is_weekend else 3),  # hourly staging — 3/day on weekdays
                (103, 1 if run_date.weekday() == 0 else 0),  # weekly — Mondays only
            ]
            for job_id, n_runs in run_schedule:
                job_name, env_id, env_name = next(
                    (j[1], j[2], j[3]) for j in dbt_jobs if j[0] == job_id
                )
                for r_idx in range(n_runs):
                    start_hour = 2 + r_idx * 6 if job_id == 102 else (1 if job_id == 101 else 3)
                    started = datetime(
                        run_date.year,
                        run_date.month,
                        run_date.day,
                        start_hour,
                        rng.randint(0, 10),
                        tzinfo=UTC,
                    )
                    duration = rng.uniform(
                        420, 900 if job_id == 101 else (180 if job_id == 102 else 1800)
                    )
                    finished = started + timedelta(seconds=duration)
                    # Credits ≈ fraction of that day's TRANSFORM_WH credits
                    credits = round(rng.uniform(0.02, 0.18 if job_id != 103 else 0.45), 6)
                    status = "error" if rng.random() < 0.04 else "success"

                    session.add(
                        DbtCloudRun(
                            run_id=dbt_run_id,
                            job_id=job_id,
                            job_name=job_name,
                            environment_id=env_id,
                            environment_name=env_name,
                            project_id=1,
                            project_name="analytics",
                            triggered_by="scheduled",
                            status=status,
                            started_at=started,
                            finished_at=finished,
                            duration_seconds=round(duration, 1),
                            models_executed=rng.randint(8, 45) if status == "success" else None,
                            credits_used=credits,
                            synced_at=synced_at,
                        )
                    )
                    dbt_run_id += 1

    # ── dbt model threshold alerts ────────────────────────────────────────
    threshold = 0.3  # demo threshold: 0.3 credits/day
    async with get_db() as session:
        for model, excess_day_offset in [("revenue_daily", 3), ("churn_features", 8)]:
            alert_day = today - timedelta(days=excess_day_offset)
            period_start_dt = datetime(
                alert_day.year, alert_day.month, alert_day.day, 0, 0, 0, tzinfo=UTC
            )
            period_end_dt = period_start_dt + timedelta(hours=23, minutes=59)
            credits_used = round(rng.uniform(threshold * 1.3, threshold * 2.2), 6)
            session.add(
                DbtModelThresholdAlert(
                    detected_at=period_end_dt,
                    dbt_model=model,
                    period_start=period_start_dt,
                    period_end=period_end_dt,
                    credits_used=credits_used,
                    threshold=threshold,
                )
            )

    # ── dbt model metadata (from manifest) ───────────────────────────────
    manifest_models = [
        (
            "orders",
            "analytics",
            "data-eng@acme.com",
            "Core order fact table",
            "incremental",
            '["finance","core"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "customers",
            "analytics",
            "data-eng@acme.com",
            "Customer dimension with LTV enrichment",
            "incremental",
            '["core"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "order_items",
            "analytics",
            None,
            "Order line-item grain",
            "incremental",
            '["finance"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "products",
            "analytics",
            "product-team@acme.com",
            "Product catalog snapshot",
            "table",
            '["catalog"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "revenue_daily",
            "analytics",
            "finance@acme.com",
            "Daily revenue rollup used by Finance BI",
            "table",
            '["finance","reporting"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "churn_features",
            "analytics",
            "ml-team@acme.com",
            "Feature store for churn prediction model",
            "incremental",
            '["ml","churn"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "ltv_model",
            "analytics",
            "ml-team@acme.com",
            "Customer lifetime value predictions",
            "table",
            '["ml"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "marketing_attribution",
            "analytics",
            "growth@acme.com",
            "Last-touch attribution for marketing spend",
            "incremental",
            '["marketing"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "inventory_snapshot",
            "analytics",
            None,
            "Daily inventory snapshot via dbt snapshot strategy",
            "snapshot",
            '["ops"]',
            "dbt_prod",
            "ANALYTICS",
        ),
        (
            "funnel_stages",
            "analytics",
            "growth@acme.com",
            "User funnel stage transitions",
            "view",
            '["marketing","product"]',
            "dbt_prod",
            "ANALYTICS",
        ),
    ]
    async with get_db() as session:
        for (
            model_name,
            project_name,
            owner,
            description,
            materialization,
            tags,
            schema_name,
            database_name,
        ) in manifest_models:
            session.add(
                DbtModelMetadata(
                    model_name=model_name,
                    project_name=project_name,
                    owner=owner,
                    description=description,
                    materialization=materialization,
                    tags=tags,
                    schema_name=schema_name,
                    database_name=database_name,
                    updated_at=now - timedelta(hours=6),
                )
            )

    # ── Resource monitors ─────────────────────────────────────────────────
    # Four monitors — two well-tuned, one approaching its limit, one exceeded
    demo_monitors = [
        {
            "name": "RM_TRANSFORM_WH",
            "credit_quota": 250.0,
            "used_credits": 238.5,  # 95.4% used → critical proximity
            "remaining_credits": 11.5,
            "level": "WAREHOUSE",
            "frequency": "MONTHLY",
            "notify_at_percentage": 75.0,
            "suspend_at_percentage": 100.0,
            "suspend_immediately_at_percentage": 110.0,
            "warehouses": json.dumps(["TRANSFORM_WH"]),
            "owner": "ACCOUNTADMIN",
        },
        {
            "name": "RM_ML_WH",
            "credit_quota": 100.0,
            "used_credits": 81.0,  # 81% used → high proximity (within 19pp of suspend)
            "remaining_credits": 19.0,
            "level": "WAREHOUSE",
            "frequency": "MONTHLY",
            "notify_at_percentage": 75.0,
            "suspend_at_percentage": 100.0,
            "suspend_immediately_at_percentage": 110.0,
            "warehouses": json.dumps(["ML_WH"]),
            "owner": "ACCOUNTADMIN",
        },
        {
            "name": "RM_COMPUTE_WH",
            "credit_quota": 50.0,
            "used_credits": 28.4,  # 56.8% used → within 75% notify threshold, medium
            "remaining_credits": 21.6,
            "level": "WAREHOUSE",
            "frequency": "MONTHLY",
            "notify_at_percentage": 75.0,
            "suspend_at_percentage": 100.0,
            "suspend_immediately_at_percentage": 110.0,
            "warehouses": json.dumps(["COMPUTE_WH"]),
            "owner": "ACCOUNTADMIN",
        },
        {
            "name": "RM_REPORTING_WH",
            "credit_quota": 25.0,
            "used_credits": 10.2,  # 40.8% used → healthy
            "remaining_credits": 14.8,
            "level": "WAREHOUSE",
            "frequency": "MONTHLY",
            "notify_at_percentage": 75.0,
            "suspend_at_percentage": 100.0,
            "suspend_immediately_at_percentage": 110.0,
            "warehouses": json.dumps(["REPORTING_WH"]),
            "owner": "ACCOUNTADMIN",
        },
    ]
    async with get_db() as session:
        for m in demo_monitors:
            session.add(
                ResourceMonitor(
                    name=m["name"],
                    credit_quota=m["credit_quota"],
                    used_credits=m["used_credits"],
                    remaining_credits=m["remaining_credits"],
                    level=m["level"],
                    frequency=m["frequency"],
                    notify_at_percentage=m["notify_at_percentage"],
                    suspend_at_percentage=m["suspend_at_percentage"],
                    suspend_immediately_at_percentage=m["suspend_immediately_at_percentage"],
                    warehouses=m["warehouses"],
                    owner=m["owner"],
                    synced_at=synced_at,
                )
            )

    # ── Report ────────────────────────────────────────────────────────────
    period_end = now
    period_start = now - timedelta(days=7)
    async with get_db() as session:
        session.add(
            ReportRecord(
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
                details_json=json.dumps(
                    {
                        "warehouses": [
                            {"name": wh, "credits": round(_jitter(base * 7, 0.15), 3)}
                            for wh, base in WAREHOUSES
                        ],
                        "top_dbt_models": [
                            {"model": m, "credits": round(rng.uniform(0.05, 0.35), 4)}
                            for m in DBT_MODELS[:5]
                        ],
                    }
                ),
            )
        )
