# Changelog

All notable changes to FrostWatch are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.1.0] - 2026-04-25

### Added
- Pull from `SNOWFLAKE.ACCOUNT_USAGE` (query history, warehouse metering, storage) on a configurable schedule
- Cost breakdown by warehouse, user, and query tag
- Top-N most expensive queries with full query text
- Anomaly detection: spend spike vs. rolling 21-day baseline per warehouse
- LLM-powered plain-English anomaly explanations and query rewrite suggestions
- BYO-LLM support: Anthropic (Claude), OpenAI (GPT-4o), Google Gemini, Ollama (local)
- Weekly digest delivery via Slack webhook and SMTP email
- Built-in APScheduler (no external cron required)
- Dark-themed web UI (React 18 + TypeScript + Vite + Tailwind CSS + Recharts)
- REST API (FastAPI) with endpoints for dashboard, queries, warehouses, anomalies, reports, settings, sync, and scheduler
- CLI: `frostwatch serve`, `sync`, `config init`, `config show`, `version`
- Docker + docker-compose single-container deployment
- YAML config file with `FROSTWATCH_` environment variable overrides
- Async SQLite persistence (SQLAlchemy 2.0 + aiosqlite)

[Unreleased]: https://github.com/arunrajiah/frostwatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arunrajiah/frostwatch/releases/tag/v0.1.0
