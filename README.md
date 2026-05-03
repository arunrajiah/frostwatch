# ❄️ FrostWatch

**Snowflake cost monitoring shouldn't cost more than the savings.**

[![CI](https://github.com/arunrajiah/frostwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/arunrajiah/frostwatch/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/frostwatch)](https://pypi.org/project/frostwatch/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Farunrajiah%2Ffrostwatch-blue)](https://ghcr.io/arunrajiah/frostwatch)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/arunrajiah?label=Sponsors&logo=github)](https://github.com/sponsors/arunrajiah)

FrostWatch is an open source, self-hostable, AI-powered cost and query observability tool for Snowflake. Point it at your Snowflake account and get instant answers to "where is all our money going?" — no SaaS contract, no percentage-of-spend pricing, no phone-home.

## Try it in 30 seconds (no Snowflake needed)

```bash
pip install frostwatch
frostwatch demo
# → open http://localhost:8000
```

`frostwatch demo` seeds the local database with 35 days of realistic synthetic data — warehouse cost trends, dbt model breakdowns, injected anomaly spikes, AI explanations, and a weekly digest — so you can explore the full UI before connecting a real Snowflake account.

## What it does

- **Cost breakdown** by warehouse, user, role, and query tag — updated on a schedule you control
- **Anomaly detection** that flags unusual spend spikes against a rolling 21-day baseline
- **Plain-English explanations** of anomalies and expensive queries, powered by your own LLM (Anthropic, OpenAI, Gemini, or a local Ollama model)
- **Query recommendations** — suggested rewrites, warehouse right-sizing, clustering candidates
- **Weekly digests** delivered to Slack or email
- **Clean web UI** — dark-themed React dashboard, no BI tool required
- **REST API** — all data accessible via `/api/*` endpoints
- **CLI** — sync, config, and server management from the terminal

## Quickstart

### Option A — Docker (recommended)

```bash
# 1. Copy and edit the config
curl -O https://raw.githubusercontent.com/arunrajiah/frostwatch/main/frostwatch.yaml.example
cp frostwatch.yaml.example frostwatch.yaml
# Edit frostwatch.yaml with your Snowflake credentials and LLM API key

# 2. Start
docker compose up -d

# 3. Open the UI
open http://localhost:8000
```

### Option B — pip

```bash
pip install frostwatch

# Initialize config
frostwatch config init
# Edit ~/.frostwatch/config.yaml with your credentials

# Start the server
frostwatch serve
```

### Option C — from source

```bash
git clone https://github.com/arunrajiah/frostwatch
cd frostwatch

# Install Python package in editable mode
pip install -e ".[dev]"

# Build the frontend
cd frontend && npm install && npm run build && cd ..

# Initialize config
frostwatch config init

# Run
frostwatch serve --reload
```

## Configuration

All config lives in `~/.frostwatch/config.yaml`. Every field can also be set via environment variable with the `FROSTWATCH_` prefix.

```yaml
snowflake_account: "xy12345.us-east-1"
snowflake_user: "FROSTWATCH_USER"
snowflake_password: "your_password"
snowflake_role: "ACCOUNTADMIN"       # needs SELECT on ACCOUNT_USAGE

llm_provider: "anthropic"            # anthropic | openai | gemini | ollama
llm_api_key: "sk-ant-..."

slack_webhook_url: "https://hooks.slack.com/services/..."
email_recipients: ["ops@example.com"]

schedule_cron: "0 8 * * 1"          # weekly digest — Monday 8am
sync_cron: "0 */6 * * *"            # data sync — every 6 hours
credits_per_dollar: 3.0              # adjust for your Snowflake contract rate
snowflake_query_limit: 500           # queries fetched per sync
```

See [`frostwatch.yaml.example`](frostwatch.yaml.example) for the full reference.

## Snowflake permissions

FrostWatch only reads from `SNOWFLAKE.ACCOUNT_USAGE`. The minimum required grant:

```sql
-- Create a dedicated role (recommended)
CREATE ROLE frostwatch_role;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE frostwatch_role;
GRANT ROLE frostwatch_role TO USER your_user;
```

The `ACCOUNTADMIN` role already has this access. No data is ever written to Snowflake.

## LLM providers

| Provider | `llm_provider` | Default model |
|---|---|---|
| Anthropic (Claude) | `anthropic` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `gpt-4o` |
| Google Gemini | `gemini` | `gemini-2.0-flash` |
| Ollama (local) | `ollama` | `llama3` — set `llm_base_url` to your Ollama server |

FrostWatch is BYO-LLM. Your data never passes through a hosted proxy — it goes directly from your server to the LLM provider using the API key you supply.

## CLI reference

```
frostwatch demo              Seed synthetic data and start server — no Snowflake needed
frostwatch serve             Start the web server (default: http://localhost:8000)
frostwatch serve --reload    Start with auto-reload for development
frostwatch sync              Run a one-off Snowflake sync
frostwatch config init       Create ~/.frostwatch/config.yaml from the example
frostwatch config show       Print current config (secrets masked)
frostwatch version           Print version
```

## API

The REST API is available under `/api`. Interactive docs are at `http://localhost:8000/docs` when the server is running.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/dashboard` | Cost summary + recent anomalies |
| `GET` | `/api/queries` | Top queries by credit usage |
| `GET` | `/api/warehouses` | Per-warehouse cost aggregates |
| `GET` | `/api/anomalies` | Detected anomalies with LLM explanations |
| `GET` | `/api/dbt` | Credit + cost breakdown by dbt model |
| `POST` | `/api/sync` | Trigger a manual Snowflake sync |
| `GET` | `/api/settings` | Current configuration |
| `PUT` | `/api/settings` | Update configuration |
| `POST` | `/api/settings/test-snowflake` | Test Snowflake connectivity |
| `POST` | `/api/reports/generate` | Generate an AI cost report |

## Architecture

```
┌─────────────┐     read-only     ┌──────────────────────────────────┐
│  Snowflake  │ ◄───────────────  │  frostwatch serve                │
│ ACCOUNT_    │                   │                                  │
│ USAGE views │                   │  FastAPI + APScheduler           │
└─────────────┘                   │  ├── /api/*  (REST)              │
                                  │  └── /       (React SPA)         │
┌─────────────┐                   │                                  │
│  LLM API    │ ◄───────────────  │  SQLite  (local cache + history) │
│ (your key)  │                   └──────────────────────────────────┘
└─────────────┘
```

FrostWatch runs entirely inside your infrastructure. The only outbound calls are to Snowflake and your chosen LLM provider.

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Sponsors

FrostWatch is free and MIT-licensed. If it saves your team money on Snowflake, please consider sponsoring to keep development going.

[![Sponsor FrostWatch](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github)](https://github.com/sponsors/arunrajiah)

| Tier | Monthly | Perks |
|------|---------|-------|
| ☕ Coffee | $5 | Warm fuzzy feeling |
| 🧊 Supporter | $25 | Name in this README |
| ❄️ Backer | $100 | Name + priority issue response |
| 🏔️ Sponsor | $500 | Logo in README + dedicated support |

<!-- sponsors --><!-- sponsors -->

## Contributing

Contributions are welcome! Please open an issue before starting large changes so we can align on direction.

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and PR guidelines
- Follow our [Code of Conduct](CODE_OF_CONDUCT.md)
- All PRs require passing CI (lint, type check, tests, frontend build) and one maintainer review

## License

[MIT](LICENSE) — free to use, modify, and self-host. See the license file for details.
