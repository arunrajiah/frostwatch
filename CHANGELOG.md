# Changelog

All notable changes to FrostWatch are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.4.1] - 2026-08-31

### Fixed

- `frostwatch demo` and `frostwatch serve` crashed on startup with `sqlite3.OperationalError: unable to open database file`: the `db_path` default `Path("")` normalizes to `Path(".")`, so the fallback to `~/.frostwatch/frostwatch.db` never ran and SQLite tried to open a directory.
- `pip install frostwatch` shipped no dashboard at all: the built React frontend was never included in the wheel, so every route outside `/api` returned 404. The wheel now bundles the frontend at `frostwatch/frontend_dist`, and the app serves it from there (source checkouts still use `frontend/dist`).
- API docs are now actually at `/api/docs`, matching what the CLI banner prints (they were at the FastAPI default `/docs`).
- The API now reports the real package version instead of a hardcoded one.

## [0.4.0] - 2026-05-08

### Added
- **Resource monitor syncing**: `RESOURCE_MONITORS_SQL` fetches all monitors from `SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS`; new `ResourceMonitor` SQLite table stores quota, usage, thresholds, assigned warehouses, and owner; upserted on every sync
- **Quota recommendations** (`frostwatch/analysis/resource_monitors.py`): per-warehouse analysis using p95 daily credits over a configurable history window; recommended quota = `ceil(p95 × 30 × (1 + buffer_pct))` rounded to a clean milestone (10, 25, 50, 100, 250 … 10 000); flags existing monitors as `uncovered`, `undersized`, `oversized`, or `adequate`; priority scoring via coefficient of variation
- **DDL generation** (`generate_monitor_sql()`): renders a complete `CREATE OR REPLACE RESOURCE MONITOR … ALTER WAREHOUSE … SET RESOURCE_MONITOR` block with inline comments; immediately copy-paste ready for a Snowflake worksheet
- **Proximity alerts** (`detect_proximity_alerts()`): compares current `used_credits / credit_quota` against notify/suspend/suspend-immediately thresholds; severity bands — `critical` (within 5 pp), `high` (within 15 pp), `medium` (beyond 15 pp but threshold ahead)
- **Per-user and per-role budget tracking** (`compute_budget_usage()`): compares actual credits from `CachedQuery` against configurable daily limits (`user_credit_budgets`, `role_credit_budgets` in config); returns spend, budget, percentage used, and over-budget flag
- **New API endpoints** (`/api/resource-monitors`):
  - `GET /api/resource-monitors` — list all synced monitors
  - `GET /api/resource-monitors/recommendations` — quota recommendations with `?history_days=` and `?buffer_pct=` params
  - `GET /api/resource-monitors/generate-sql?warehouse=` — copy-paste DDL for a specific warehouse
  - `GET /api/resource-monitors/proximity-alerts` — monitors near their limits, sorted by used %
  - `GET /api/resource-monitors/budgets?days=` — per-user and per-role spend vs budget
- **New config fields**: `user_credit_budgets` and `role_credit_budgets` (dict[str, float]) for per-user/role daily credit limits
- **Demo mode enriched**: seeds 4 resource monitors with realistic usage levels — one critical (95 % used), one high (81 %), one medium (57 %), one healthy (41 %)
- **New documentation**: `docs/resource-monitors.md` — full guide on quota recommendations, DDL generation, proximity alerts, and budget tracking; `docs/api.md` extended with all 5 new endpoints
- Bump version to 0.4.0

## [0.3.0] - 2026-05-07

### Added
- **dbt Cloud integration** (`frostwatch/dbt_cloud/client.py`): async client for the dbt Cloud REST API v2; pulls runs, jobs, and environments with full pagination; `POST /api/dbt/sync-cloud` persists run metadata and attributes Snowflake credits to each run by matching dbt-tagged queries inside the run time window
- **Cost breakdown by job and environment**: `GET /api/dbt/jobs` and `GET /api/dbt/environments` aggregate credits, run counts, avg duration, and last-run status from synced dbt Cloud runs
- **dbt model spend threshold alerts**: configurable `dbt_model_credit_threshold` (credits/day per model); detected automatically at the end of every Snowflake sync; stored in new `DbtModelThresholdAlert` table; retrieved via `GET /api/dbt/threshold-alerts`
- **dbt manifest enrichment** (`frostwatch/dbt_cloud/manifest.py`): parse a `manifest.json` to extract owner, description, materialization, tags, schema, and database per model; `POST /api/dbt/manifest` upserts this into a new `DbtModelMetadata` table; `GET /api/dbt/metadata` returns the enriched catalogue
- **GitHub Actions workflow** (`.github/workflows/dbt-cost-comment.yml`): posts a dbt model cost summary + threshold alert table as a PR comment after every dbt run; uses `peter-evans/create-or-update-comment` to edit rather than duplicate
- **New DB models**: `DbtCloudRun`, `DbtModelThresholdAlert`, `DbtModelMetadata` — created automatically on first startup
- **New config fields**: `dbt_cloud_account_id`, `dbt_cloud_api_token` (secret), `dbt_model_credit_threshold`; `dbt_cloud_api_token` redacted in `save_config`
- **Demo mode enriched**: seeds 30 days of dbt Cloud runs across 3 jobs / 2 environments, 2 threshold alert examples, and manifest metadata for all 10 demo dbt models (owner, description, materialization, tags)
- Bump version to 0.3.0

## [0.2.1] - 2026-05-07

### Added
- **Partition pruning analysis** (`frostwatch/analysis/pruning.py`): detect query patterns that scan an excessive fraction of micro-partitions; groups by SQL fingerprint, computes avg pruning ratio (`partitions_scanned / partitions_total`), severity (`medium` ≥ 50 %, `high` ≥ 70 %, `critical` ≥ 90 %); small tables (< 100 avg partitions) excluded to avoid noise
- **`GET /api/insights/pruning`** endpoint: returns patterns sorted by impact (pruning ratio × total credits × executions); supports `?days=`, `?limit=`, `?min_partitions=`, `?min_ratio=`
- `partitions_scanned` and `partitions_total` columns added to `CachedQuery` (inline SQLite migration applied on first start — no manual migration needed)
- `QUERY_HISTORY_SQL` updated to fetch `partitions_scanned` and `partitions_total` from `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`
- Demo mode seeds realistic partition stats — 25 % of queries with poor pruning (ratio 0.65–1.0), 75 % with good pruning (0.05–0.45)
- Docs: "Partition pruning analysis" section added to `docs/insights.md`; pruning endpoint with full request/response reference added to `docs/api.md`

## [0.2.0] - 2026-05-04

### Added
- **Query fingerprinting** (`frostwatch/analysis/fingerprint.py`): normalize SQL to a canonical form (strip literals, collapse IN-lists, uppercase) and group near-identical queries by MD5 fingerprint; `build_fingerprints()` returns per-pattern stats (total/avg credits, execution count, first/last seen, top warehouse/user)
- **Week-over-week regression detection** (`detect_regressions()`): compares average per-execution credits this week vs last week per fingerprint; flags patterns that regressed beyond a configurable threshold with `medium / high / critical` severity
- **Cost forecasting** (`frostwatch/analysis/forecast.py`): per-warehouse ordinary least-squares regression over configurable history window; projects daily credits and USD cost for the next 1–30 days with trend (`up / down / stable`) and confidence (`low / medium / high`) labels
- **AI rewrite suggestions**: `POST /api/insights/rewrites` submits a `query_id` to the configured LLM and returns a structured Markdown report (optimized SQL, root cause, recommendations, estimated savings %); results are persisted and returned idempotently
- **New `/api/insights` endpoints**:
  - `GET /api/insights/fingerprints` — top query patterns by total credits (`?days=`, `?limit=`)
  - `GET /api/insights/regressions` — week-over-week cost regressions (`?threshold=`, `?limit=`)
  - `GET /api/insights/forecasts` — per-warehouse cost projections (`?days_ahead=`, `?history_days=`)
  - `POST /api/insights/rewrites` — request an AI rewrite for a query
  - `GET /api/insights/rewrites/{query_id}` — fetch a previously generated rewrite
- **`QueryRewrite` SQLite model**: persists LLM-generated rewrite suggestions; created automatically on first startup
- **Demo mode enriched**: `frostwatch demo` seeds two pre-baked AI rewrites (ML features query + MERGE query) so the Insights page is immediately useful

## [0.1.7] - 2026-05-03

### Added
- **`frostwatch demo`** CLI command: seeds the local SQLite database with 35 days of deterministic synthetic data (warehouse metrics, ~500 queries, dbt model attributions, injected anomaly spikes with LLM explanations, weekly report) and starts the server — no Snowflake account or LLM API key required
- `frostwatch/demo/seed.py`: async `seed_demo()` helper with `random.Random(42)` for reproducible data; includes weekend dips, a 6.5× TRANSFORM_WH spend spike, and realistic log-normal query execution times
- Updated README: "Try it in 30 seconds" quickstart block, `frostwatch demo` in CLI reference, `/api/dbt` in API table
- Updated ROADMAP.md to reflect shipped items through v0.1.7

## [0.1.6] - 2026-04-28

### Added
- **dbt integration**: automatically parse `query_tag` JSON set by dbt-snowflake to extract model names; `dbt_model` column added to `cached_queries` table with inline migration for existing databases
- **`GET /api/dbt`** endpoint: returns credit, cost, query count, and avg execution time broken down by dbt model name; supports `?days=` parameter
- **dbt Models page** in the web UI: summary cards, horizontal bar chart (top 15 models), full sortable table
- `dbt_model` field surfaced in `GET /api/queries` responses
- 10 unit tests for dbt query tag parsing covering flat, nested, and edge-case formats
- **MkDocs documentation site** deployed to GitHub Pages (`https://arunrajiah.github.io/frostwatch/`) with Installation, Configuration, dbt Integration, and API Reference pages
- CI workflow (`.github/workflows/docs.yml`) auto-deploys docs on every push to `main` that touches `docs/` or `mkdocs.yml`

### Security
- Redact Slack webhook URL from `GET /api/settings` response; return `slack_webhook_url_set: bool` instead of the raw secret (matching pattern used for `llm_api_key` and Snowflake password)

## [0.1.5] - 2026-04-26

### Fixed
- Snowflake client: add 30s login timeout + 60s network timeout; wrap connection errors with readable messages instead of raw tracebacks
- CORS: make allowed origins configurable via `cors_origins` config field (default keeps localhost dev origins; production deployments add their URL)

### Added
- `cors_origins` config field and `frostwatch.yaml.example` entry
- `sync_cron`, `snowflake_query_limit` documented in `frostwatch.yaml.example`

## [0.1.4] - 2026-04-26

### Changed
- README: badges, corrected clone URL, accurate LLM model names, API table, expanded Snowflake permissions

## [0.1.3] - 2026-04-26

### Fixed
- Dockerfile: copy README.md into builder stage so hatch build works after readme was added to pyproject.toml

## [0.1.2] - 2026-04-26

### Changed
- PyPI package metadata: added README, MIT license, author, keywords, and trove classifiers
- Added Changelog and Docker Image URLs to project metadata

## [0.1.0] - 2026-04-25

### Added
- Pull from `SNOWFLAKE.ACCOUNT_USAGE` (query history, warehouse metering, storage) on a configurable schedule
- Cost breakdown by warehouse, user, and query tag
- Top-N most expensive queries with full query text
- Anomaly detection: spend spike vs. rolling 21-day baseline per warehouse
- LLM-powered plain-English anomaly explanations generated per anomaly at sync time
- BYO-LLM support: Anthropic (Claude Sonnet), OpenAI (GPT-4o), Google Gemini, Ollama (local)
- Weekly digest delivery via Slack webhook and SMTP email
- Built-in APScheduler with independently configurable sync cron and report cron
- Dark-themed web UI (React 18 + TypeScript + Vite 7 + Tailwind CSS + Recharts)
- REST API (FastAPI) with endpoints for dashboard, queries, warehouses, anomalies, reports, settings, sync, and scheduler
- `POST /api/settings/test-snowflake` and `POST /api/settings/test-email` connection test endpoints
- Rate limiting on `POST /api/sync` (10 requests/minute via slowapi)
- CLI: `frostwatch serve`, `sync`, `config init`, `config show`, `version`
- Docker + docker-compose single-container deployment
- YAML config file with `FROSTWATCH_` environment variable overrides
- Async SQLite persistence (SQLAlchemy 2.0 + aiosqlite)
- Settings UI: SMTP configuration, Snowflake and SMTP connection test buttons, configurable sync schedule and query fetch limit
- Configurable `snowflake_query_limit` (default 500) passed through to Snowflake query
- Security scanning: CodeQL, Trivy, pip-audit, npm-audit, dependency-review in CI

[Unreleased]: https://github.com/arunrajiah/frostwatch/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/arunrajiah/frostwatch/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/arunrajiah/frostwatch/compare/v0.1.3...v0.1.5
[0.1.3]: https://github.com/arunrajiah/frostwatch/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/arunrajiah/frostwatch/compare/v0.1.1...v0.1.2
[0.1.0]: https://github.com/arunrajiah/frostwatch/releases/tag/v0.1.0
