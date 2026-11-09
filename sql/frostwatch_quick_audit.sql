-- =============================================================================
-- FrostWatch Quick Audit: find Snowflake savings in 60 seconds, zero install.
--
-- How to use: paste this whole file into a Snowsight worksheet and click
-- "Run All" (Cmd/Ctrl + Shift + Enter). The last result is your findings list,
-- sorted by estimated monthly savings, with the SQL to fix each one.
--
-- Read-only. Needs a role that can read SNOWFLAKE.ACCOUNT_USAGE
-- (ACCOUNTADMIN, or: GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE <role>).
--
-- Want more checks (repeated queries, Time Travel bloat, unused tables,
-- clustering costs), a shareable HTML report, and continuous monitoring?
--   pip install frostwatch && frostwatch audit
--   https://github.com/arunrajiah/frostwatch   (free, MIT, self-hosted)
-- =============================================================================

SET credit_price = 3.00;   -- USD per credit: change to your contract rate
SET days = 30;             -- history window

SHOW WAREHOUSES;
SET wh_qid = LAST_QUERY_ID();

WITH
wh AS (
    SELECT "name" AS name, "size" AS size, "auto_suspend" AS auto_suspend,
           "resource_monitor" AS resource_monitor,
           DECODE(UPPER(REPLACE("size", '-', '')),
                  'XSMALL', 1, 'SMALL', 2, 'MEDIUM', 4, 'LARGE', 8, 'XLARGE', 16,
                  '2XLARGE', 32, 'XXLARGE', 32, '3XLARGE', 64, 'XXXLARGE', 64,
                  '4XLARGE', 128, '5XLARGE', 256, '6XLARGE', 512, 0) AS cph
    FROM TABLE(RESULT_SCAN($wh_qid))
),
metering AS (
    SELECT warehouse_name, SUM(credits_used) AS credits,
           COUNT(DISTINCT DATE_TRUNC('hour', start_time)) AS active_hours
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -$days, CURRENT_TIMESTAMP())
    GROUP BY 1
),
resumes AS (
    SELECT warehouse_name, COUNT(*) AS resumes
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
    WHERE timestamp >= DATEADD('day', -$days, CURRENT_TIMESTAMP())
      AND event_name = 'RESUME_WAREHOUSE' AND event_state = 'COMPLETED'
    GROUP BY 1
),
qstats AS (
    SELECT warehouse_name, COUNT(*) AS queries,
           APPROX_PERCENTILE(execution_time, 0.95) / 1000 AS p95_exec_s,
           APPROX_PERCENTILE(bytes_scanned, 0.95) AS p95_bytes,
           SUM(bytes_spilled_to_remote_storage) AS spill_remote,
           SUM(bytes_spilled_to_local_storage) AS spill_local
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -$days, CURRENT_TIMESTAMP())
      AND warehouse_name IS NOT NULL AND execution_status = 'SUCCESS'
    GROUP BY 1
),
cs AS (
    SELECT SUM(credits_used_cloud_services) AS cs_credits,
           SUM(credits_used_cloud_services + credits_adjustment_cloud_services) AS cs_billed,
           SUM(credits_used_compute) AS compute_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE usage_date >= DATEADD('day', -$days, CURRENT_DATE())
),
findings AS (
    -- 1. Auto-suspend higher than 60s: idle tail after every resume is billed
    SELECT 'Auto-suspend set too high' AS finding, wh.name AS object_name,
           (wh.auto_suspend - 60) * COALESCE(r.resumes, m.active_hours / 2) / 3600
             * wh.cph * $credit_price * 30 / $days AS est_monthly_savings_usd,
           'AUTO_SUSPEND = ' || wh.auto_suspend || 's, ' || COALESCE(r.resumes, 0)
             || ' resumes in ' || $days || ' days' AS detail,
           'ALTER WAREHOUSE "' || wh.name || '" SET AUTO_SUSPEND = 60;' AS fix_sql
    FROM wh JOIN metering m ON m.warehouse_name = wh.name
    LEFT JOIN resumes r ON r.warehouse_name = wh.name
    WHERE wh.auto_suspend > 60

    UNION ALL
    -- 2. Auto-suspend disabled on a warehouse that bills around the clock
    SELECT 'Warehouse never suspends', wh.name,
           m.credits * $credit_price * 30 / $days * 0.5,
           'AUTO_SUSPEND is off; billed in ' || m.active_hours || ' of '
             || ($days * 24) || ' hours (savings assume half is idle)',
           'ALTER WAREHOUSE "' || wh.name || '" SET AUTO_SUSPEND = 60;'
    FROM wh JOIN metering m ON m.warehouse_name = wh.name
    WHERE COALESCE(wh.auto_suspend, 0) = 0 AND m.active_hours >= 0.8 * $days * 24

    UNION ALL
    -- 3. Oversized: Medium+ running only small, fast queries with no spilling
    SELECT 'Warehouse looks oversized', wh.name,
           m.credits * $credit_price * 30 / $days * 0.3,
           wh.size || ': ' || q.queries || ' queries, p95 ' || ROUND(q.p95_exec_s, 1)
             || 's, p95 scan ' || ROUND(q.p95_bytes / POWER(1024, 2)) || ' MB, no spilling',
           'ALTER WAREHOUSE "' || wh.name || '" SET WAREHOUSE_SIZE = '''
             || DECODE(wh.cph, 4, 'SMALL', 8, 'MEDIUM', 16, 'LARGE', 32, 'XLARGE',
                       64, 'XXLARGE', 128, 'XXXLARGE', 256, 'X4LARGE', 512, 'X5LARGE')
             || ''';  -- try for a week, compare runtimes'
    FROM wh JOIN metering m ON m.warehouse_name = wh.name
    JOIN qstats q ON q.warehouse_name = wh.name
    WHERE wh.cph >= 4 AND q.queries >= 100 AND q.p95_exec_s < 10
      AND q.p95_bytes < POWER(1024, 3) AND q.spill_remote = 0
      AND q.spill_local < POWER(1024, 3)

    UNION ALL
    -- 4. Remote spilling: undersized for some queries (performance risk)
    SELECT 'Queries spilling to remote storage', q.warehouse_name, 0,
           ROUND(q.spill_remote / POWER(1024, 3)) || ' GB spilled to remote storage',
           'SELECT query_id, bytes_spilled_to_remote_storage FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE warehouse_name = '''
             || q.warehouse_name || ''' ORDER BY 2 DESC LIMIT 20;'
    FROM qstats q
    WHERE q.spill_remote > 10 * POWER(1024, 3)

    UNION ALL
    -- 5. Cloud services billed above the free 10 percent
    SELECT 'Paying for cloud services above the free 10 percent', 'ACCOUNT',
           cs.cs_billed * $credit_price * 30 / $days * 0.5,
           ROUND(cs.cs_billed, 1) || ' cloud services credits billed ('
             || ROUND(100 * cs.cs_credits / NULLIF(cs.compute_credits, 0)) || ' pct of compute)',
           'SELECT query_type, COUNT(*), SUM(credits_used_cloud_services) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY GROUP BY 1 ORDER BY 3 DESC LIMIT 20;'
    FROM cs
    WHERE cs.cs_billed > 0

    UNION ALL
    -- 6. No resource monitor: no ceiling on a runaway query
    SELECT 'Warehouse with no spending cap', wh.name, 0,
           'Spends ~$' || ROUND(m.credits * $credit_price * 30 / $days) || '/month with no resource monitor',
           'CREATE RESOURCE MONITOR "FW_' || wh.name || '_MONTHLY" WITH CREDIT_QUOTA = '
             || GREATEST(10, CEIL(m.credits * 30 / $days * 1.5))
             || ' FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY TRIGGERS ON 80 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND; ALTER WAREHOUSE "'
             || wh.name || '" SET RESOURCE_MONITOR = "FW_' || wh.name || '_MONTHLY";'
    FROM wh JOIN metering m ON m.warehouse_name = wh.name
    WHERE wh.resource_monitor IS NULL OR wh.resource_monitor = 'null'
)
SELECT ROW_NUMBER() OVER (ORDER BY est_monthly_savings_usd DESC, finding) AS rank,
       finding,
       object_name,
       ROUND(est_monthly_savings_usd, 2) AS est_monthly_savings_usd,
       detail,
       fix_sql
FROM findings
WHERE est_monthly_savings_usd >= 5 OR est_monthly_savings_usd = 0
ORDER BY rank;
