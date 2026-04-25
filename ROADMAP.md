# FrostWatch Roadmap

This document describes what FrostWatch does today and where it's headed. If you want to pick up a task, open an issue and mention this roadmap item so we can coordinate.

---

## v0.1 — Current (shipped)

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

---

## v0.2 — Query deep-dive

Richer analysis of individual expensive queries.

- [ ] Query profile integration (read from `QUERY_HISTORY` join `QUERY_ACCELERATION_HISTORY`)
- [ ] Partition pruning analysis — detect full-table scans that could be pruned
- [ ] Repeated / near-identical query detection (query fingerprinting)
- [ ] "Most improved" and "most regressed" queries week-over-week
- [ ] Query tag extraction for dbt model attribution (`dbt_*` tags → model name)

---

## v0.3 — dbt integration

First-class support for dbt model cost attribution.

- [ ] Auto-detect dbt query tags (`dbt_invocation_id`, `dbt_node_id`)
- [ ] Cost breakdown by dbt model, tag, and invocation
- [ ] Identify the most expensive dbt models
- [ ] Warning when a model crosses a configurable spend threshold
- [ ] Optional: pull dbt manifest for richer model metadata

---

## v0.4 — Resource monitor management

FrostWatch helps set up Snowflake's own cost controls.

- [ ] Read existing resource monitors from `RESOURCE_MONITORS` view
- [ ] Recommend new resource monitors based on observed warehouse spend patterns
- [ ] Generate the `CREATE RESOURCE MONITOR` SQL, ready to apply
- [ ] Alert when a warehouse approaches its resource monitor limit

---

## v0.5 — Multi-account and team features

Useful for platform teams managing multiple Snowflake accounts.

- [ ] Multi-account support (one FrostWatch instance, N accounts)
- [ ] Per-user cost attribution dashboard (who spent what)
- [ ] Team/cost-center tagging via configurable role or tag mapping
- [ ] Weekly cost digest per team, sent to different Slack channels
- [ ] Read-only viewer mode (no config changes from the UI)

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
- [ ] Auth (optional htpasswd or OIDC via a proxy)
- [ ] Helm chart for Kubernetes
- [ ] OpenTelemetry traces from FrostWatch itself
- [ ] Alert routing: PagerDuty, OpsGenie, webhook
- [ ] Historical report archive with diff ("spend is up 12% vs last month")
- [ ] GitHub Sponsors page

---

## Ideas parking lot (not yet scoped)

- Terraform / Pulumi provider for resource monitors
- Snowpark cost tracking
- Data Sharing egress cost analysis
- VS Code extension: inline cost estimate while writing SQL
- GitHub Action: cost estimate on PRs that touch SQL models

---

If you want to contribute to any of these, open an issue and reference the roadmap item. We'll scope it and create a tracking issue together.
