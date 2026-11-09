"""Synthetic inputs for `frostwatch audit --demo` and the demo UI."""

from __future__ import annotations

from frostwatch.analysis.advisor import GB, TB, AuditInputs


def demo_inputs() -> AuditInputs:
    return AuditInputs(
        warehouses=[
            {
                "name": "TRANSFORM_WH",
                "size": "Large",
                "auto_suspend": 600,
                "resource_monitor": "null",
                "min_cluster_count": 1,
            },
            {
                "name": "BI_WH",
                "size": "Medium",
                "auto_suspend": 300,
                "resource_monitor": "BI_MONTHLY",
                "min_cluster_count": 1,
            },
            {
                "name": "LOADING_WH",
                "size": "X-Small",
                "auto_suspend": 60,
                "resource_monitor": "null",
                "min_cluster_count": 1,
            },
            {
                "name": "ADHOC_WH",
                "size": "Small",
                "auto_suspend": None,
                "resource_monitor": "null",
                "min_cluster_count": 1,
            },
            {
                "name": "DATA_SCIENCE_WH",
                "size": "X-Large",
                "auto_suspend": 120,
                "resource_monitor": "null",
                "min_cluster_count": 1,
            },
        ],
        metering=[
            {"warehouse_name": "TRANSFORM_WH", "credits": 1450, "active_hours": 400},
            {"warehouse_name": "BI_WH", "credits": 610, "active_hours": 520},
            {"warehouse_name": "LOADING_WH", "credits": 90, "active_hours": 300},
            {"warehouse_name": "ADHOC_WH", "credits": 1380, "active_hours": 690},
            {"warehouse_name": "DATA_SCIENCE_WH", "credits": 900, "active_hours": 150},
        ],
        resumes=[
            {"warehouse_name": "TRANSFORM_WH", "resumes": 250},
            {"warehouse_name": "BI_WH", "resumes": 600},
            {"warehouse_name": "LOADING_WH", "resumes": 2800},
            {"warehouse_name": "DATA_SCIENCE_WH", "resumes": 150},
        ],
        wh_stats=[
            {
                "warehouse_name": "BI_WH",
                "warehouse_size": "Medium",
                "queries": 48000,
                "p95_exec_s": 3.2,
                "p95_bytes_scanned": 180 * 1024**2,
                "spill_local_bytes": 0,
                "spill_remote_bytes": 0,
                "queued_s": 300,
                "exec_s": 90000,
            },
            {
                "warehouse_name": "TRANSFORM_WH",
                "warehouse_size": "Large",
                "queries": 21000,
                "p95_exec_s": 240,
                "p95_bytes_scanned": 60 * GB,
                "spill_local_bytes": 900 * GB,
                "spill_remote_bytes": 240 * GB,
                "queued_s": 1200,
                "exec_s": 1_100_000,
            },
            {
                "warehouse_name": "DATA_SCIENCE_WH",
                "warehouse_size": "X-Large",
                "queries": 3100,
                "p95_exec_s": 410,
                "p95_bytes_scanned": 120 * GB,
                "spill_local_bytes": 40 * GB,
                "spill_remote_bytes": 0,
                "queued_s": 144000,
                "exec_s": 720000,
            },
        ],
        repeated=[
            {
                "query_hash": "9f2c1a7be04d55e1",
                "warehouse_name": "BI_WH",
                "warehouse_size": "Medium",
                "sample_text": "SELECT region, SUM(amount) FROM analytics.marts.fct_orders WHERE order_ts >= DATEADD(day, -7, CURRENT_TIMESTAMP()) GROUP BY 1",
                "runs": 8640,
                "exec_s": 120960,
            },
            {
                "query_hash": "4b0e77d1c9aa3f20",
                "warehouse_name": "TRANSFORM_WH",
                "warehouse_size": "Large",
                "sample_text": "SELECT COUNT(*) FROM raw.events.page_views WHERE event_date = CURRENT_DATE()",
                "runs": 720,
                "exec_s": 28800,
            },
        ],
        cloud_services=[
            {
                "compute_credits": 4430,
                "cloud_services_credits": 690,
                "cloud_services_adjustment": -443,
                "credits_billed": 4677,
            },
        ],
        time_travel=[
            {
                "table_catalog": "ANALYTICS",
                "table_schema": "STAGING",
                "table_name": "EVENTS_RAW",
                "active_bytes": 800 * GB,
                "time_travel_bytes": 2.1 * TB,
                "failsafe_bytes": 4.6 * TB,
                "is_transient": "NO",
            },
            {
                "table_catalog": "RAW",
                "table_schema": "SALESFORCE",
                "table_name": "OPPORTUNITY_HISTORY",
                "active_bytes": 120 * GB,
                "time_travel_bytes": 400 * GB,
                "failsafe_bytes": 900 * GB,
                "is_transient": "NO",
            },
        ],
        unused_tables=[
            {
                "table_catalog": "ARCHIVE",
                "table_schema": "LEGACY",
                "table_name": "WEB_EVENTS_2022",
                "active_bytes": 3.2 * TB,
            },
            {
                "table_catalog": "ANALYTICS",
                "table_schema": "SCRATCH",
                "table_name": "TMP_BACKFILL_JAN",
                "active_bytes": 650 * GB,
            },
        ],
        clustering=[
            {
                "database_name": "ANALYTICS",
                "schema_name": "MARTS",
                "table_name": "FCT_ORDERS",
                "credits": 180,
            },
        ],
    )
