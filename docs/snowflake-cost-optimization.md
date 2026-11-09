---
description: A practical Snowflake cost optimization checklist with the SQL to find and fix each problem. Auto-suspend, warehouse sizing, result cache, cloud services, Time Travel, unused tables, resource monitors.
---

# Snowflake cost optimization checklist

Most Snowflake bills carry 15 to 40 percent of avoidable spend, and it hides in the same handful of places. Here is the checklist we use, ordered by how often it pays off, with the query to find each issue and the fix. Every item is automated by [`frostwatch audit`](savings-advisor.md) and the [Quick Audit SQL](quick-audit-sql.md).

!!! tip "Skip the reading"
    `pip install frostwatch && frostwatch audit -c <connection>` runs all of these in about a minute and writes a report with dollar estimates. [Sample report](sample-audit.html).

## 1. Set auto-suspend to 60 seconds

Snowflake bills a minimum of 60 seconds per resume, then per second. A warehouse with `AUTO_SUSPEND = 600` burns up to nine idle minutes after every burst of work. On a Large warehouse (8 credits/hour) that resumes 10 times a day, that is about 12 credits a day for nothing.

```sql
SHOW WAREHOUSES;  -- check the auto_suspend column
ALTER WAREHOUSE my_wh SET AUTO_SUSPEND = 60;
```

Exception: BI warehouses that benefit from a warm local disk cache can justify 5 to 10 minutes. Measure before and after.

## 2. Never leave auto-suspend off

`AUTO_SUSPEND = 0` or `NULL` means the warehouse runs until someone stops it. It is the single most expensive one-line mistake in Snowflake.

## 3. Right-size warehouses that only run small queries

Each size up doubles the credit rate. If a Medium or larger warehouse only runs queries that finish in a few seconds and scan little data, one size down usually costs half with barely any slowdown. Look at p95 runtime and bytes scanned per warehouse in `QUERY_HISTORY`, and make sure nothing spills.

## 4. Upsize (or fix) only what spills to remote storage

`BYTES_SPILLED_TO_REMOTE_STORAGE > 0` means the query ran out of memory and local disk. These queries can run many times slower. Fix the query, or route only those jobs to a bigger warehouse: upsizing everything to fix a few queries is a classic overspend.

## 5. Treat queuing with clusters, not size

If queries spend a lot of time in `QUEUED_OVERLOAD_TIME`, you have a concurrency problem. A multi-cluster warehouse (Enterprise) with `SCALING_POLICY = 'ECONOMY'` adds capacity only while the queue exists. A bigger single cluster costs more all day.

## 6. Make the result cache work for dashboards

Identical queries normally hit the 24-hour result cache for free. They miss it when the SQL uses `CURRENT_TIMESTAMP()`, `RANDOM()` or similar, when `USE_CACHED_RESULT = FALSE`, or when the table changes between runs. Group `QUERY_HISTORY` by `QUERY_HASH`, look for hashes that ran hundreds of times and still scanned data, and fix the SQL or materialize the result.

## 7. Stay under the free 10 percent of cloud services

Cloud services credits are free up to 10 percent of daily compute. Above that you pay. Check `METERING_DAILY_HISTORY`: `credits_used_cloud_services + credits_adjustment_cloud_services` is the billed part. Usual causes: very chatty tools issuing thousands of tiny queries or `SHOW` commands, and huge compilation workloads.

## 8. Cut Time Travel and Fail-safe on churny tables

Tables rebuilt from scratch or heavily updated keep every old version for the retention period, plus 7 days of Fail-safe. In `TABLE_STORAGE_METRICS`, look for tables where `time_travel_bytes + failsafe_bytes` exceeds `active_bytes`. If the table can be rebuilt from source, make it transient and set `DATA_RETENTION_TIME_IN_DAYS = 0` or `1`. In dbt, `+transient: true`.

## 9. Find large tables nobody reads

On Enterprise Edition, `ACCESS_HISTORY` tells you which tables were read. Big tables with no reads in 90 days are candidates to drop or unload to object storage. Confirm with owners first.

## 10. Put a resource monitor on every warehouse

Resource monitors are free and are the only hard stop for a runaway query or a loop gone wrong. A monthly quota at about 1.5x normal usage, notify at 80 percent and suspend at 100 percent, costs nothing in normal months.

```sql
CREATE RESOURCE MONITOR wh_monthly WITH CREDIT_QUOTA = 500 FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 80 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE my_wh SET RESOURCE_MONITOR = wh_monthly;
```

FrostWatch's [resource monitor page](resource-monitors.md) sizes quotas from your real p95 spend.

## 11. Review automatic clustering spend

Automatic clustering runs serverless and can quietly cost more than the queries it speeds up. Check `AUTOMATIC_CLUSTERING_HISTORY` per table, and confirm queries actually filter on the clustering key.

## Keep it from creeping back

A one-off cleanup decays in weeks: a new dbt model, a new dashboard, a new hire with a Large warehouse. [FrostWatch](index.md) watches continuously: anomaly alerts, cost per dbt model, week-over-week query regressions, AI query rewrites and a weekly Slack digest. Free, MIT licensed, self-hosted.
