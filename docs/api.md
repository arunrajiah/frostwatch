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

## Insights

The `/api/insights` group provides deeper analysis of query patterns, cost trends, and AI-powered optimization suggestions.

### `GET /api/insights/fingerprints`

Groups queries by normalized SQL fingerprint and returns the top patterns by total credits.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Look-back window (1–90) |
| `limit` | int | 20 | Max patterns to return (1–100) |

**Response** — array of `QueryFingerprintRecord`:

```json
[
  {
    "fingerprint": "a3f1b2c4...",
    "canonical_sql": "SELECT * FROM ORDERS WHERE STATUS = '?' AND CREATED_AT >= ?",
    "example_query_id": "01b2c3d4-...",
    "total_executions": 142,
    "total_credits": 0.8431,
    "avg_credits": 0.005938,
    "avg_execution_ms": 3210.5,
    "first_seen": "2026-04-01T00:00:00Z",
    "last_seen": "2026-04-30T18:42:00Z",
    "most_common_warehouse": "COMPUTE_WH",
    "most_common_user": "TRANSFORMER"
  }
]
```

### `GET /api/insights/regressions`

Returns query patterns whose average per-execution cost rose this week compared to last week.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | 2.0 | Min ratio (this week avg / last week avg) to flag (1.1–20.0) |
| `limit` | int | 10 | Max patterns to return (1–50) |

**Response** — array of `QueryRegressionRecord`:

```json
[
  {
    "fingerprint": "a3f1b2c4...",
    "canonical_sql_preview": "SELECT * FROM ORDERS ...",
    "example_query_id": "01b2c3d4-...",
    "avg_credits_this_week": 0.012,
    "avg_credits_last_week": 0.003,
    "regression_ratio": 4.0,
    "executions_this_week": 38,
    "executions_last_week": 41,
    "most_common_warehouse": "COMPUTE_WH",
    "severity": "high"
  }
]
```

Severity levels: `medium` (ratio ≥ 2×), `high` (≥ 3×), `critical` (≥ 5×).

### `GET /api/insights/forecasts`

Projects per-warehouse credit and USD cost for the next N days using ordinary least-squares regression on historical warehouse metrics.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days_ahead` | int | 7 | Days to project ahead (1–30) |
| `history_days` | int | 30 | History window used to fit the model (7–90) |

**Response** — array of `CostForecastPoint`:

```json
[
  {
    "warehouse_name": "COMPUTE_WH",
    "forecast_date": "2026-05-05",
    "predicted_credits": 4.21,
    "predicted_cost_usd": 1.40,
    "trend": "up",
    "confidence": "high",
    "projected_30d_credits": 126.3,
    "projected_30d_cost_usd": 42.1
  }
]
```

`trend` is `up`, `down`, or `stable`. `confidence` is `low` (< 7 data points), `medium` (7–13), or `high` (≥ 14).

### `POST /api/insights/rewrites`

Submits an expensive query to your configured LLM and returns an optimization report. Results are persisted and returned idempotently — calling this endpoint twice for the same `query_id` returns the cached result without making a second LLM call.

**Request body:**

```json
{ "query_id": "01b2c3d4-..." }
```

**Response** — `QueryRewriteResponse`:

```json
{
  "id": 1,
  "query_id": "01b2c3d4-...",
  "fingerprint": "a3f1b2c4...",
  "rewrite_suggestion": "## Rewrite\n```sql\nSELECT id, status, ...```\n\n## Root Cause\n...\n\n## Recommendations\n- Add clustering key on STATUS\n...\n\n## Estimated Savings\n40–60% credit reduction",
  "generated_at": "2026-05-04T10:00:00Z"
}
```

Returns `503` if no LLM provider is configured, `404` if the `query_id` is not found, `404` if no rewrite exists yet (use POST to generate one).

### `GET /api/insights/pruning`

Returns query patterns with poor partition pruning efficiency, sorted by impact (pruning ratio × total credits × executions).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 30 | Look-back window (1–90) |
| `limit` | int | 20 | Max patterns to return (1–100) |
| `min_partitions` | int | 100 | Min average `partitions_total` to include (filters out small tables) |
| `min_ratio` | float | 0.5 | Min average pruning ratio (0.1–1.0) to flag |

**Response** — array of `PartitionPruningRecord`:

```json
[
  {
    "fingerprint": "a3f1b2c4...",
    "canonical_sql_preview": "SELECT * FROM ORDERS WHERE STATUS = '?'",
    "example_query_id": "01b2c3d4-...",
    "total_executions": 87,
    "executions_analyzed": 85,
    "avg_pruning_ratio": 0.92,
    "avg_partitions_scanned": 4140.0,
    "avg_partitions_total": 4500.0,
    "avg_credits": 0.0182,
    "total_credits": 1.547,
    "most_common_warehouse": "COMPUTE_WH",
    "most_common_user": "ANALYST_ALICE",
    "severity": "critical",
    "recommendation": "Add a clustering key on the high-cardinality filter column(s)..."
  }
]
```

Severity levels: `medium` (ratio ≥ 0.5), `high` (≥ 0.7), `critical` (≥ 0.9).

### `GET /api/insights/rewrites/{query_id}`

Fetches the most recent rewrite suggestion for a query. Returns `404` if none has been generated yet.

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
