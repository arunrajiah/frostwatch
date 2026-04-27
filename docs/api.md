# REST API Reference

FrostWatch exposes a REST API at `/api`. The interactive Swagger UI is available at `http://localhost:8000/docs`.

## Dashboard

### `GET /api/dashboard`

Returns the 7-day and 30-day summary used by the dashboard page.

**Response**

```json
{
  "total_credits_7d": 12.34,
  "total_cost_7d": 4.11,
  "total_credits_30d": 55.2,
  "total_cost_30d": 18.4,
  "top_warehouses": [
    { "name": "COMPUTE_WH", "credits": 40.1, "cost_usd": 13.37, "pct_of_total": 72.6 }
  ],
  "top_users": [...],
  "recent_anomalies": [...],
  "last_synced": "2026-04-28T08:00:00Z",
  "query_count_7d": 1240
}
```

## Queries

### `GET /api/queries`

Returns the most expensive queries ordered by credits consumed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 7 | Lookback window (1–365) |
| `limit` | int | 50 | Max rows returned (1–500) |

**Response** — array of `QueryRecord`:

```json
[
  {
    "query_id": "01b2c3d4-...",
    "warehouse_name": "COMPUTE_WH",
    "user_name": "TRANSFORMER",
    "role_name": "SYSADMIN",
    "execution_time_ms": 4521.0,
    "bytes_scanned": 1073741824,
    "credits_used": 0.000832,
    "start_time": "2026-04-27T14:22:01Z",
    "end_time": "2026-04-27T14:22:05Z",
    "query_text_preview": "SELECT * FROM ...",
    "query_tag": "{\"app\":\"dbt\",\"node_id\":\"model.proj.orders\"}",
    "dbt_model": "orders",
    "status": "SUCCESS"
  }
]
```

## Warehouses

### `GET /api/warehouses`

Returns credit and query aggregates per warehouse.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Lookback window (1–365) |

### `GET /api/warehouses/timeseries`

Returns daily credit usage per warehouse.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Lookback window (1–365) |
| `warehouse` | string | — | Filter to a single warehouse |

## dbt Models

### `GET /api/dbt`

Returns credit and performance breakdown by dbt model name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Lookback window (1–365) |

**Response** — array of `DbtModelAgg`, sorted by `total_credits` descending:

```json
[
  {
    "dbt_model": "orders",
    "total_credits": 0.0412,
    "total_cost_usd": 0.0137,
    "query_count": 48,
    "avg_execution_ms": 3210.5
  }
]
```

## Anomalies

### `GET /api/anomalies`

Returns detected spend anomalies with optional LLM explanations.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Lookback window (1–365) |

## Reports

### `GET /api/reports`

Returns previously generated weekly digest reports.

### `POST /api/reports/generate`

Triggers an on-demand digest report generation.

## Sync

### `POST /api/sync`

Triggers a Snowflake data sync in the background. Rate-limited to 10 requests/minute.

**Response:** `{"status": "started"}`

### `GET /api/sync/status`

Returns the status of the most recent sync run.

```json
{
  "status": "idle",
  "last_run_at": "2026-04-28T08:00:00Z",
  "last_error": null,
  "rows_synced": 482
}
```

## Settings

### `GET /api/settings`

Returns the current configuration (credentials are redacted — only `_set` booleans are returned for secrets).

### `PUT /api/settings`

Updates configuration fields. The server restarts the LLM provider and scheduler on success.

### `POST /api/settings/test-snowflake`

Tests the current Snowflake connection by running `SELECT 1`.

### `POST /api/settings/test-email`

Tests the current SMTP configuration by connecting and issuing `EHLO`.

## Scheduler

### `GET /api/scheduler/jobs`

Returns the list of scheduled APScheduler jobs (sync cron and report cron).

### `POST /api/scheduler/trigger`

Manually triggers the report generation job.
