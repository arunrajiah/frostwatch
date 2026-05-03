# Changelog

All notable changes to FrostWatch are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
