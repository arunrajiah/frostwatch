# ❄️ FrostWatch

**Snowflake cost monitoring shouldn't cost more than the savings.**

FrostWatch is an open source, self-hostable, AI-powered cost and query observability tool for Snowflake. Point it at your Snowflake account and get instant answers to "where is all our money going?" — no SaaS contract, no percentage-of-spend pricing, no phone-home.

![Dashboard screenshot](docs/screenshot-dashboard.png)

## What it does

- **Cost breakdown** by warehouse, user, role, and query tag — updated on a schedule you control
- **Anomaly detection** that flags unusual spend spikes against a rolling baseline
- **Plain-English explanations** of anomalies and expensive queries, powered by your own LLM (Anthropic, OpenAI, Gemini, or a local Ollama model)
- **Query recommendations** — suggested rewrites, warehouse right-sizing, clustering candidates
- **Weekly digests** delivered to Slack or email
- **Clean web UI** — no BI tool required

## Quickstart (under 5 minutes)

### Option A — Docker (recommended)

```bash
# 1. Copy and edit the config
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
# Edit ~/.frostwatch/config.yaml

# Start the server
frostwatch serve
```

### Option C — from source

```bash
git clone https://github.com/your-org/frostwatch
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

All config lives in `~/.frostwatch/config.yaml` (or the path you set via `FROSTWATCH_DATA_DIR`). Every field is also settable via environment variable with the `FROSTWATCH_` prefix.

```yaml
snowflake_account: "xy12345.us-east-1"
snowflake_user: "your_user"
snowflake_password: "your_password"
snowflake_role: "ACCOUNTADMIN"     # needs SELECT on ACCOUNT_USAGE

llm_provider: "anthropic"          # anthropic | openai | gemini | ollama
llm_api_key: "sk-ant-..."

slack_webhook_url: "https://hooks.slack.com/services/..."
schedule_cron: "0 8 * * 1"        # weekly Monday 8am digest
credits_per_dollar: 3.0            # adjust for your contract rate
```

See [`frostwatch.yaml.example`](frostwatch.yaml.example) for the full reference.

## Snowflake permissions

FrostWatch only reads from `SNOWFLAKE.ACCOUNT_USAGE`. The minimum required grant:

```sql
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE your_role;
```

The `ACCOUNTADMIN` role already has this. For a least-privilege setup, create a dedicated role.

## LLM providers

| Provider | Set `llm_provider` to | Notes |
|---|---|---|
| Anthropic (Claude) | `anthropic` | Default model: `claude-opus-4-7` |
| OpenAI | `openai` | Default model: `gpt-4o` |
| Google Gemini | `gemini` | Default model: `gemini-1.5-pro` |
| Ollama (local) | `ollama` | Default model: `llama3`; set `llm_base_url` |

FrostWatch is BYO-LLM. We never proxy your data through a hosted service.

## CLI reference

```
frostwatch serve             Start the web server (default: http://localhost:8000)
frostwatch sync              Run a one-off sync without starting the server
frostwatch config init       Create ~/.frostwatch/config.yaml from the example
frostwatch config show       Print current config (secrets masked)
frostwatch version           Print version
```

## Architecture

```
┌─────────────┐     HTTPS     ┌──────────────────────────────────┐
│  Snowflake  │ ◄──────────── │  frostwatch serve                │
│ ACCOUNT_    │               │                                  │
│ USAGE views │               │  FastAPI + APScheduler           │
└─────────────┘               │  ├── /api/*  (REST endpoints)    │
                              │  └── /       (React SPA)         │
┌─────────────┐               │                                  │
│  LLM API    │ ◄──────────── │  SQLite (local cache + history)  │
│ (your key)  │               └──────────────────────────────────┘
└─────────────┘
```

FrostWatch runs entirely inside your infrastructure. The only outbound calls are to Snowflake and your LLM provider — both using credentials you supply.

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions are welcome. Please open an issue before starting large changes.

- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
