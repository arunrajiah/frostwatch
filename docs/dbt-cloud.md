# dbt Cloud Integration

Connect FrostWatch to the dbt Cloud API to get run-level cost attribution, per-job and per-environment breakdowns, model spend threshold alerts, and manifest-enriched model metadata.

## Configuration

```yaml
# ~/.frostwatch/config.yaml
dbt_cloud_account_id: "12345"          # Your dbt Cloud account ID (Settings → Account)
dbt_cloud_api_token: "dbtc_..."        # Service token with Viewer access
dbt_model_credit_threshold: 0.5        # Alert when a model exceeds this many credits/day (0 = disabled)
```

Or via environment variables:

```bash
export FROSTWATCH_DBT_CLOUD_ACCOUNT_ID=12345
export FROSTWATCH_DBT_CLOUD_API_TOKEN=dbtc_...
export FROSTWATCH_DBT_MODEL_CREDIT_THRESHOLD=0.5
```

## Syncing run metadata

```bash
curl -X POST http://localhost:8000/api/dbt/sync-cloud
```

Returns `{"runs_synced": N, "jobs_enriched": N, "environments_enriched": N}`.

FrostWatch pulls the last 30 days of runs and attributes Snowflake credits to each run by summing dbt-tagged queries whose `start_time` falls inside the run window.

## Cost breakdown by job and environment

| Endpoint | What it shows |
|----------|--------------|
| `GET /api/dbt/jobs` | Credits, cost, run count, avg duration, last-run status per job |
| `GET /api/dbt/environments` | Credits, cost, run count, distinct jobs per environment |
| `GET /api/dbt/runs` | Individual runs with full metadata, newest first |

All three endpoints accept a `?days=` parameter (1–90, default 30).

## Spend threshold alerts

Set `dbt_model_credit_threshold` in your config to a positive value. After every Snowflake sync, FrostWatch checks each dbt model's total credits for the current calendar day. If any model exceeds the threshold, an alert is created.

```
GET /api/dbt/threshold-alerts
```

Example response:

```json
[
  {
    "id": 1,
    "detected_at": "2026-05-04T23:59:00Z",
    "dbt_model": "revenue_daily",
    "period_start": "2026-05-04T00:00:00Z",
    "period_end": "2026-05-04T23:59:00Z",
    "credits_used": 0.612,
    "threshold": 0.3
  }
]
```

## Manifest enrichment

Upload your `manifest.json` to add owner, description, materialization type, and tags to every model in FrostWatch.

```bash
curl -X POST http://localhost:8000/api/dbt/manifest \
     -H "Content-Type: application/json" \
     --data-binary @target/manifest.json
```

Automate this in CI (add after `dbt run` or `dbt compile`):

```yaml
- name: Upload dbt manifest to FrostWatch
  run: |
    curl -X POST "${{ secrets.FROSTWATCH_URL }}/api/dbt/manifest" \
         -H "Content-Type: application/json" \
         --data-binary @target/manifest.json
```

Retrieve enriched metadata:

```
GET /api/dbt/metadata
```

## PR cost comment (GitHub Actions)

The bundled workflow `.github/workflows/dbt-cost-comment.yml` posts a dbt model cost table + threshold alerts as a PR comment after every dbt run.

**Setup:**

1. Add a `FROSTWATCH_URL` repository secret.
2. In the workflow file, update `workflow_run.workflows` to match the name of your dbt workflow.
3. Ensure FrostWatch is reachable from your CI runner.

The comment is edited on subsequent runs — one comment per PR, always up to date.

### Required GitHub Actions permissions

```yaml
permissions:
  pull-requests: write
```

### Third-party actions used

- `peter-evans/find-comment@v3`
- `peter-evans/create-or-update-comment@v4`
