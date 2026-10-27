# Chaos Genius alternative

**Looking for a maintained, open source replacement for Chaos Genius to watch your Snowflake spend? FrostWatch is MIT licensed, self-hosted, and actively developed.**

The open source [Chaos Genius](https://github.com/chaos-genius/chaos_genius) repository was archived in September 2024 and is no longer maintained. If you used it to keep an eye on Snowflake costs, or you are looking for an open source option after evaluating Chaos Genius's commercial Snowflake product, this page explains what carries over and how to switch.

## Is FrostWatch the right replacement?

Chaos Genius was a **general-purpose** anomaly detection and root cause engine: you pointed it at any data source and defined the KPIs and dimensions yourself. FrostWatch is **Snowflake-specific**: it reads `SNOWFLAKE.ACCOUNT_USAGE` directly, so cost metrics, dimensions, and baselines work with no modeling on your side.

- **Switch to FrostWatch** if the main thing you monitored was Snowflake spend, warehouse usage, or query cost.
- **Look elsewhere** if you monitored business KPIs (daily active users, revenue, failure rates) or data outside Snowflake. FrostWatch does not cover those.

## Feature mapping

| What you used in Chaos Genius | FrostWatch equivalent |
|---|---|
| Anomaly detection on a cost KPI | Per-warehouse spend anomaly detection against a rolling 21-day baseline, with severity levels |
| Multidimensional drill-downs | Cost by warehouse, user, role, query tag, and dbt model |
| Automated root cause analysis | Plain-English LLM explanations for each anomaly, query fingerprinting to find the SQL patterns driving spend, and week-over-week regression detection |
| Smart alerting | Weekly digests to Slack or email, dbt model spend thresholds, and resource monitor limit warnings |
| Forecasting (was on the Chaos Genius roadmap) | Per-warehouse credit forecasts for the next 1 to 30 days |
| Self-hosted with Docker | Self-hosted with Docker or `pip install`; data stays in your infrastructure |

FrostWatch also adds Snowflake-specific tools Chaos Genius did not have:

- **dbt model cost attribution**, dbt Cloud job and environment breakdowns, and a cost summary posted on pull requests
- **AI query rewrites** with optimized SQL and estimated savings
- **Resource monitor recommendations** with ready-to-run `CREATE RESOURCE MONITOR` DDL
- **Per-user and per-role budgets**
- **Bring your own LLM**: Anthropic, OpenAI, Gemini, or a fully local Ollama model

## Migrating

There is no data to export. FrostWatch reads history straight from Snowflake's `ACCOUNT_USAGE` views, which keep up to a year of query and metering history, so your first sync already has a baseline.

**1. Try it with synthetic data first (no Snowflake needed):**

```bash
pip install frostwatch
frostwatch demo
# open http://localhost:8000
```

**2. Create a read-only role.** FrostWatch never writes to Snowflake:

```sql
CREATE ROLE frostwatch_role;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE frostwatch_role;
GRANT ROLE frostwatch_role TO USER your_user;
```

**3. Configure and start:**

```bash
frostwatch config init    # creates ~/.frostwatch/config.yaml
frostwatch serve          # starts on http://localhost:8000
```

Add your Snowflake credentials, an LLM key (or an Ollama URL), and your Slack webhook or SMTP settings to the config. See [Configuration](configuration.md) for every option, or [Installation](installation.md) for Docker.

## Questions

Open an [issue](https://github.com/arunrajiah/frostwatch/issues). If something you relied on in Chaos Genius is missing, tell us: it helps decide what goes on the [roadmap](https://github.com/arunrajiah/frostwatch/blob/main/ROADMAP.md).
