# Configuration

FrostWatch is configured via `~/.frostwatch/config.yaml`. Every field can also be set via an environment variable prefixed `FROSTWATCH_` — environment variables take precedence over the YAML file.

## Full reference

```yaml
# ── Snowflake connection ──────────────────────────────────────────────────────
snowflake_account: "xy12345.us-east-1"     # Your Snowflake account identifier
snowflake_user: "your_username"
snowflake_password: "your_password"        # Or FROSTWATCH_SNOWFLAKE_PASSWORD
snowflake_warehouse: "COMPUTE_WH"
snowflake_database: "SNOWFLAKE"            # Built-in SNOWFLAKE database
snowflake_schema: "ACCOUNT_USAGE"          # Leave as-is
snowflake_role: "ACCOUNTADMIN"             # Needs SELECT on ACCOUNT_USAGE

# ── LLM configuration ────────────────────────────────────────────────────────
# Supported providers: anthropic | openai | gemini | ollama
llm_provider: "anthropic"
llm_model: ""                              # Leave empty to use provider default
llm_api_key: "sk-ant-..."                  # Or FROSTWATCH_LLM_API_KEY
llm_base_url: "http://localhost:11434"     # Only used for ollama provider

# ── Alerts ────────────────────────────────────────────────────────────────────
slack_webhook_url: ""                      # https://hooks.slack.com/services/...
email_smtp_host: ""                        # e.g. smtp.gmail.com
email_smtp_port: 587
email_smtp_user: ""
email_smtp_password: ""
email_recipients:
  - "data-team@yourcompany.com"

# ── Scheduling ────────────────────────────────────────────────────────────────
schedule_cron: "0 8 * * 1"    # Weekly digest (default: Monday 8am)
sync_cron: "0 */6 * * *"      # Data sync (default: every 6 hours)
snowflake_query_limit: 500    # Max queries fetched per sync

# ── Anomaly detection ─────────────────────────────────────────────────────────
alert_threshold_multiplier: 3.0  # Flag spend > 3× rolling baseline

# ── Cost ──────────────────────────────────────────────────────────────────────
credits_per_dollar: 3.0           # Adjust for your contract rate

# ── Server ────────────────────────────────────────────────────────────────────
cors_origins:
  - "http://localhost:5173"
  - "http://127.0.0.1:5173"
  # Add your deployment URL for production:
  # - "https://frostwatch.yourcompany.com"

# ── Storage ───────────────────────────────────────────────────────────────────
data_dir: "~/.frostwatch"         # SQLite database and logs location
```

## LLM providers

| Provider | `llm_provider` | Default model | Notes |
|----------|---------------|---------------|-------|
| Anthropic | `anthropic` | `claude-sonnet-4-6` | Recommended |
| OpenAI | `openai` | `gpt-4o` | |
| Google Gemini | `gemini` | `gemini-2.0-flash` | |
| Ollama (local) | `ollama` | `llama3` | Set `llm_base_url` to your Ollama endpoint |

LLM is only used to generate anomaly explanations. FrostWatch functions without it — anomalies will still be detected, just without plain-English summaries.

## Environment variables

All config fields are available as env vars by uppercasing the field name and adding the `FROSTWATCH_` prefix:

```bash
export FROSTWATCH_SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export FROSTWATCH_SNOWFLAKE_PASSWORD=secret
export FROSTWATCH_LLM_API_KEY=sk-ant-...
```

This is the recommended approach for Docker and Kubernetes deployments.

## Production deployment

For production add your deployment URL to `cors_origins`:

```yaml
cors_origins:
  - "https://frostwatch.yourcompany.com"
```

Or via env var (comma-separated):

```bash
FROSTWATCH_CORS_ORIGINS=https://frostwatch.yourcompany.com
```
