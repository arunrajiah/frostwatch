# FrostWatch Roadmap

This document describes what FrostWatch does today and where it's headed. If you want to pick up a task, open an issue and mention this roadmap item so we can coordinate.

---

## v0.1 — Bootstrap (shipped)

The minimum useful product. Gets a team from zero to "oh, *that's* where the money is going" in under 30 minutes.

- [x] Pull from `SNOWFLAKE.ACCOUNT_USAGE` (query history, warehouse metering, storage)
- [x] Cost breakdown by warehouse, user, and query tag
- [x] Top-N most expensive queries with full query text
- [x] Anomaly detection: spend spike vs. rolling 21-day baseline per warehouse
- [x] LLM-powered plain-English anomaly explanations
- [x] LLM query rewrite and warehouse right-sizing suggestions
- [x] BYO-LLM: Anthropic, OpenAI, Google Gemini, Ollama (local)
- [x] Weekly digest — Slack webhook and SMTP email
- [x] Built-in APScheduler (no external cron required)
- [x] Dark-themed web UI (React + Tailwind)
- [x] CLI: `frostwatch serve`, `sync`, `config init/show`
- [x] Docker + docker-compose deployment
- [x] YAML config + `FROSTWATCH_` env var overrides
- [x] **dbt model attribution** — parse `query_tag` JSON to map credits → dbt models (v0.1.6)
- [x] **dbt Models page** in the UI — bar chart + sortable table (v0.1.6)
- [x] **`frostwatch demo`** — 30-second try-it experience with no Snowflake account needed (v0.1.7)
- [x] **MkDocs documentation site** on GitHub Pages (v0.1.6)
- [x] **Security**: redact Slack webhook URL from settings API (v0.1.6)

---

## v0.2 — Query deep-dive

Richer analysis of individual expensive queries.

- [ ] Query fingerprinting — detect repeated / near-identical queries, surface patterns driving spend
- [ ] AI rewrite suggestions — Claude/GPT reviews top-5 expensive queries, suggests rewrites, clustering keys, filter pushdowns
- [ ] Partition pruning analysis — detect full-table scans that could be pruned
- [ ] "Most improved" and "most regressed" queries week-over-week
- [ ] Cost forecasting — project next month's spend based on 90-day trend

---

## v0.3 — dbt integration (deeper)

First-class support for dbt model cost attribution beyond tag parsing.

- [ ] dbt Cloud integration — pull run metadata directly from dbt Cloud API
- [ ] Cost breakdown by dbt invocation, job, and environment
- [ ] Warning when a model crosses a configurable spend threshold
- [ ] Optional: pull dbt manifest for richer model metadata (owner, description, materialization)
- [ ] GitHub Actions integration — post dbt job cost summary as PR comment after each `dbt run`

---

## v0.4 — Resource monitor management

FrostWatch helps set up Snowflake's own cost controls.

- [ ] Read existing resource monitors from `RESOURCE_MONITORS` view
- [ ] Recommend new resource monitors based on observed warehouse spend patterns
- [ ] Generate the `CREATE RESOURCE MONITOR` SQL, ready to apply
- [ ] Alert when a warehouse approaches its resource monitor limit
- [ ] Per-user and per-role credit budget tracking

---

## v0.5 — Multi-account and team features

Useful for platform teams managing multiple Snowflake accounts.

- [ ] Multi-account support (one FrostWatch instance, N accounts)
- [ ] Per-user cost attribution dashboard
- [ ] Team/cost-center tagging via configurable role or tag mapping
- [ ] Weekly cost digest per team, sent to different Slack channels
- [ ] Read-only viewer mode (no config changes from the UI)
- [ ] SSO / OIDC authentication

---

## v0.6 — Storage and clustering

Extend beyond compute credits to storage and automatic clustering.

- [ ] Storage trend analysis (database, schema, table level)
- [ ] Automatic clustering credit breakdown by table
- [ ] Materialized view refresh cost analysis
- [ ] Recommendations for tables that would benefit from clustering keys

---

## v1.0 — Production-hardened

Ready for teams who want to run this seriously.

- [ ] PostgreSQL backend option (for high-cardinality query histories)
- [ ] Helm chart for Kubernetes
- [ ] OpenTelemetry traces from FrostWatch itself
- [ ] Alert routing: PagerDuty, OpsGenie, webhook
- [ ] Historical report archive with diff ("spend is up 12% vs last month")

---

## Ideas parking lot (not yet scoped)

- Terraform / Pulumi provider for resource monitors
- Snowpark cost tracking
- Data Sharing egress cost analysis
- VS Code extension: inline cost estimate while writing SQL
- Native Grafana data source plugin
- Snowflake Streamlit in a Snowflake app variant

---

If you want to contribute to any of these, open an issue and reference the roadmap item. We'll scope it and create a tracking issue together.
