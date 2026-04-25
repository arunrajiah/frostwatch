# Changelog

All notable changes to FrostWatch are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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

[Unreleased]: https://github.com/arunrajiah/frostwatch/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/arunrajiah/frostwatch/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/arunrajiah/frostwatch/compare/v0.1.1...v0.1.2
[0.1.0]: https://github.com/arunrajiah/frostwatch/releases/tag/v0.1.0
