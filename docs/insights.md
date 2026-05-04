# Query Insights

The Insights feature set (introduced in v0.2.0) gives you a deeper understanding of *which query patterns* are driving Snowflake spend, *how that spend has changed*, and *what to do about it* — all without writing SQL yourself.

## Query fingerprinting

FrostWatch normalizes every query in your history to a canonical form:

1. Strip `--` and `/* */` comments
2. Replace string literals with `'?'`
3. Collapse `IN (...)` value lists to `IN (?)`
4. Replace numeric literals with `?`
5. Collapse whitespace and uppercase

The result is an MD5 fingerprint that groups queries that differ only in bind values or formatting into a single pattern. For example, these three queries all map to the same fingerprint:

```sql
SELECT * FROM orders WHERE id = 123
SELECT * FROM orders WHERE id = 456
SELECT * FROM orders WHERE id = 789
```

The **Insights → Fingerprints** page shows the top patterns by total credits, with per-pattern stats: total and average credits, execution count, first/last seen, and the most frequent warehouse and user.

**API endpoint:** `GET /api/insights/fingerprints?days=30&limit=20`

## Week-over-week regression detection

FrostWatch compares the average credits per execution for each fingerprint between the current week and the previous week. Patterns that grew beyond a configurable threshold are flagged with a severity label:

| Ratio (this week / last week) | Severity |
|-------------------------------|----------|
| 2× – 2.9× | `medium` |
| 3× – 4.9× | `high` |
| ≥ 5× | `critical` |

This catches situations where a query hasn't changed in code but is suddenly scanning much more data — a sign of missing filters, table bloat, or clustering drift.

**API endpoint:** `GET /api/insights/regressions?threshold=2.0&limit=10`

## Cost forecasting

FrostWatch fits an ordinary least-squares regression to each warehouse's daily credit history and projects forward. Each forecast point includes:

- **Predicted credits** and **USD cost** for each future day
- **Trend** — `up`, `down`, or `stable` (based on the regression slope)
- **Confidence** — `low` (fewer than 7 data points), `medium` (7–13), or `high` (14+)
- **Projected 30-day totals** — helpful for budget planning

Forecasts use the `credits_per_dollar` value from your config (default: `3.0`).

**API endpoint:** `GET /api/insights/forecasts?days_ahead=7&history_days=30`

## AI query rewrites

Submit any query ID to get an LLM-generated optimization report. The report includes:

- **Rewrite** — optimized SQL with inline comments explaining each change
- **Root Cause** — why the original query is expensive (1–2 sentences)
- **Recommendations** — clustering keys, filter pushdowns, warehouse right-sizing (bullet list)
- **Estimated Savings** — rough credit reduction as a percentage range

Rewrite results are persisted and returned idempotently — calling the endpoint again for the same query ID returns the cached result without a second LLM call.

!!! info "LLM required"
    AI rewrites require a configured LLM provider (`llm_provider` + `llm_api_key` in your config). Run `frostwatch demo` to see pre-baked example rewrites without an API key.

**API endpoints:**

```
POST /api/insights/rewrites          { "query_id": "01b2c3d4-..." }
GET  /api/insights/rewrites/{id}     Fetch a previously generated rewrite
```

## Demo mode

`frostwatch demo` pre-seeds two realistic rewrite examples — an ML features query and a MERGE statement — so the Insights page is immediately populated when you try the demo. No LLM API key required.

```bash
pip install frostwatch
frostwatch demo
# → open http://localhost:8000 → Insights
```
