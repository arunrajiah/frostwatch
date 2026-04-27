# dbt Integration

FrostWatch automatically detects dbt model costs without any extra configuration. It parses the `query_tag` field that dbt sets on every Snowflake query and groups credits and performance metrics by model name.

## How it works

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

## Enabling query tags in dbt

dbt sets `query_tag` automatically for Snowflake connections. Verify your `profiles.yml` includes the Snowflake adapter:

```yaml
my_project:
  target: prod
  outputs:
    prod:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: TRANSFORMER
      database: ANALYTICS
      warehouse: TRANSFORM_WH
      schema: dbt_prod
      threads: 4
      # query_tag is set automatically by dbt-snowflake >= 1.0
```

No additional configuration is needed — dbt-snowflake sets `query_tag` on every query by default from version 1.0 onwards.

## The dbt Models page

Once FrostWatch has synced data containing dbt query tags, the **dbt Models** page (sidebar → Package icon) shows:

- **Models detected** — total number of distinct dbt models observed
- **Total credits** — Snowflake credits consumed across all dbt models
- **Total queries** — number of dbt model runs
- **Bar chart** — top 15 models by credit consumption
- **Detail table** — all models with credits, USD cost, query count, and average execution time

## Backfilling existing data

After upgrading to a FrostWatch version with dbt support, trigger a manual sync to backfill `dbt_model` for any queries already in the local database:

```bash
frostwatch sync
# or click Sync Now in the sidebar
```

The sync upsert updates the `dbt_model` field on every re-synced query, so existing rows will be enriched automatically.

## Supported node types

Only `model` nodes are tracked. Seeds (`seed.*`), snapshots (`snapshot.*`), tests (`test.*`), and other node types are ignored and counted as non-dbt queries.
