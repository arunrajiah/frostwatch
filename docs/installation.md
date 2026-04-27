# Installation

## Requirements

- Python 3.11 or later
- A Snowflake account with `SELECT` on `SNOWFLAKE.ACCOUNT_USAGE` (see [Permissions](#snowflake-permissions))

## Install via pip

```bash
pip install frostwatch
```

## Install via Docker

```bash
docker pull ghcr.io/arunrajiah/frostwatch:latest
```

## Install from source

```bash
git clone https://github.com/arunrajiah/frostwatch.git
cd frostwatch
pip install -e ".[dev]"

# Build the frontend (optional — only needed if developing the UI)
cd frontend && npm install && npm run build && cd ..
```

## First-time setup

```bash
frostwatch config init   # creates ~/.frostwatch/config.yaml with defaults
```

Edit `~/.frostwatch/config.yaml` and fill in your Snowflake credentials and LLM API key, then:

```bash
frostwatch serve         # API + UI on http://localhost:8000
```

On first start FrostWatch will not have any data — click **Sync Now** in the sidebar to pull the last 30 days of query history from Snowflake.

## Snowflake permissions

FrostWatch only needs read access to the `ACCOUNT_USAGE` schema. Create a dedicated role:

```sql
CREATE ROLE frostwatch;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE frostwatch;
GRANT ROLE frostwatch TO USER my_service_user;
```

Then set `snowflake_role: frostwatch` in your config.

## CLI reference

| Command | Description |
|---------|-------------|
| `frostwatch serve` | Start the API server (default port 8000) |
| `frostwatch sync` | Run a one-off Snowflake data sync |
| `frostwatch config init` | Create default config file |
| `frostwatch config show` | Print current resolved config |
| `frostwatch version` | Print installed version |
