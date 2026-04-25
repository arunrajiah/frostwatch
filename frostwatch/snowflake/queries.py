QUERY_HISTORY_SQL = """
SELECT
    query_id,
    warehouse_name,
    user_name,
    role_name,
    database_name,
    schema_name,
    execution_time AS execution_time_ms,
    bytes_scanned,
    credits_used_cloud_services AS credits_used,
    start_time,
    end_time,
    query_text,
    query_tag,
    execution_status AS status
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE DATEDIFF('day', start_time, CURRENT_TIMESTAMP) <= %(days)s
  AND execution_status = 'SUCCESS'
  AND query_type NOT IN ('SHOW', 'DESCRIBE')
ORDER BY credits_used_cloud_services DESC
LIMIT 500
"""

WAREHOUSE_METERING_SQL = """
SELECT
    warehouse_name,
    DATE(start_time) AS usage_date,
    SUM(credits_used) AS credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE DATEDIFF('day', start_time, CURRENT_TIMESTAMP) <= %(days)s
GROUP BY warehouse_name, DATE(start_time)
ORDER BY usage_date DESC, credits_used DESC
"""

WAREHOUSE_EVENTS_SQL = """
SELECT
    warehouse_name,
    event_name,
    event_reason,
    event_state,
    timestamp,
    user_name,
    role_name,
    cluster_number,
    query_id
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
WHERE DATEDIFF('day', timestamp, CURRENT_TIMESTAMP) <= %(days)s
ORDER BY timestamp DESC
LIMIT 1000
"""

STORAGE_USAGE_SQL = """
SELECT
    usage_date,
    average_stage_bytes,
    average_database_bytes,
    average_failsafe_bytes
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
ORDER BY usage_date DESC
LIMIT 1
"""
