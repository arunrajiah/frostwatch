# dbt Integration

FrostWatch provides two layers of dbt integration:

1. **Automatic model attribution** — parse the `query_tag` Snowflake sets on every dbt query and group credits by model name. Zero config required.
2. **dbt Cloud deep-dive** — connect to the dbt Cloud API to get run-level metadata, cost breakdown by job and environment, spend threshold alerts, and manifest-enriched model metadata.

---

## Automatic model attribution

When dbt runs a model against Snowflake, it sets the `QUERY_TAG` session parameter to a JSON string such as:

```json
{
  "app": "dbt",
  "dbt_version": "1.8.0",
  "profile_name": "my_project",
  "target_name": "prod",
  "node_id": "model.my_project.orders"
}
```

FrostWatch parses this tag during each sync and extracts the model name from `node_id`. Both the flat format above and the nested `dbt_snowflake_query_tags` wrapper are supported.

dbt sets `query_tag` automatically for Snowflake connections from dbt-snowflake v1.0 onwards — no extra configuration needed.

### The dbt Models page

Once FrostWatch has synced data containing dbt query tags, the **dbt Models** page shows:

- **Models detected** — total number of distinct dbt models observed
- **Total credits** — Snowflake credits consumed across all dbt models
- **Bar chart** — top 15 models by credit consumption
- **Detail table** — credits, USD cost, query count, and average execution time per model

### Backfilling existing data

```bash
frostwatch sync
# or click Sync Now in the sidebar
```

The sync upsert updates `dbt_model` on every re-synced query, so existing rows are enriched automatically.

### Supported node types

Only `model` nodes are tracked. Seeds (`seed.*`), snapshots (`snapshot.*`), tests (`test.*`), and other node types are ignored.

---

## dbt Cloud integration

### Setup

Add the following to your `~/.frostwatch/config.yaml`:

```yaml
dbt_cloud_account_id: "12345"           # Your dbt Cloud account ID
dbt_cloud_api_token: "dbtc_..."         # Service token with read access
dbt_model_credit_threshold: 0.5        # Alert when a model exceeds 0.5 credits/day (0 = disabled)
```

Or via environment variables:

```bash
export FROSTWATCH_DBT_CLOUD_ACCOUNT_ID=12345
export FROSTWATCH_DBT_CLOUD_API_TOKEN=dbtc_...
export FROSTWATCH_DBT_MODEL_CREDIT_THRESHOLD=0.5
```

### Syncing dbt Cloud metadata

Trigger a one-off sync from the dbt Cloud API:

```bash
curl -X POST http://localhost:8000/api/dbt/sync-cloud
```

This pulls the last 30 days of runs, enriches them with job and environment names, and attributes Snowflake credits to each run by matching dbt-tagged queries inside the run time window.

### Cost breakdown by job and environment

`GET /api/dbt/jobs` — credits, cost, run count, avg duration, and last-run status per job.

`GET /api/dbt/environments` — credits, cost, run count, and distinct job count per environment.

### Spend threshold alerts

When `dbt_model_credit_threshold` is set (> 0), FrostWatch checks at the end of every Snowflake sync whether any dbt model exceeded its daily credit limit. Violations are stored and returned by `GET /api/dbt/threshold-alerts`.

Set a per-model threshold in your config:

```yaml
dbt_model_credit_threshold: 0.5   # flag any model that uses > 0.5 credits today
```

### Manifest enrichment

Upload your `manifest.json` to enrich the dbt model catalogue with owner, description, materialization type, and tags — metadata that isn't available in Snowflake's `QUERY_HISTORY`.

```bash
curl -X POST http://localhost:8000/api/dbt/manifest \
     -H "Content-Type: application/json" \
     --data-binary @target/manifest.json
```

Returns `{"models_upserted": N}`. The enriched catalogue is available at `GET /api/dbt/metadata`.

You can automate this in your dbt CI pipeline:

```yaml
# In your dbt GitHub Actions workflow, after dbt compile or dbt run:
- name: Upload manifest to FrostWatch
  run: |
    curl -X POST "${{ secrets.FROSTWATCH_URL }}/api/dbt/manifest" \
         -H "Content-Type: application/json" \
         --data-binary @target/manifest.json
```

### GitHub Actions — PR cost comments

The bundled workflow `.github/workflows/dbt-cost-comment.yml` posts a dbt model cost summary and threshold alert table as a PR comment after every dbt run.

**Setup:**

1. Add a `FROSTWATCH_URL` repository secret pointing to your FrostWatch instance.
2. Edit the `workflow_run.workflows` trigger to match the name of your dbt workflow.
3. Ensure your FrostWatch instance is reachable from GitHub Actions (or use a self-hosted runner on the same network).

The comment is edited (not duplicated) on subsequent runs using `peter-evans/create-or-update-comment`.
