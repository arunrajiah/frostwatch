# Resource Monitor Management

FrostWatch v0.4 adds end-to-end resource monitor management: it reads your existing Snowflake monitors, analyses warehouse spend patterns, recommends optimal quotas, generates copy-paste DDL, and alerts you when a monitor is approaching its limit.

---

## What are resource monitors?

A Snowflake **resource monitor** is a named object that enforces a credit quota on one or more virtual warehouses. When a warehouse reaches the configured percentage of its quota, Snowflake can:

- **Notify** — send an email to account admins
- **Suspend** — gracefully stop new queries when running queries finish
- **Suspend immediately** — kill all running queries and suspend the warehouse

Resource monitors are the primary mechanism for preventing runaway costs in Snowflake. FrostWatch automates the tedious parts: analysing historical spend, choosing the right quota, and writing the SQL.

---

## Viewing existing monitors

After a sync, navigate to **Resource Monitors** in the sidebar to see all monitors cached from `SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS`. For each monitor you'll see:

- Current quota, used credits, and remaining credits
- Assigned warehouses
- Trigger thresholds (notify / suspend / suspend-immediately)
- Reset frequency (MONTHLY, DAILY, WEEKLY, YEARLY)

!!! tip
    If you have no resource monitors yet, this list will be empty — but the **Recommendations** tab will still work from your warehouse metering history.

---

## Recommendations

The **Recommendations** tab analyses the last 30 days of warehouse metering history (configurable) and suggests a monthly credit quota for each warehouse:

```
monthly_quota = p95_daily_credits × 30 × (1 + buffer_pct)
```

The quota is then rounded up to the nearest clean milestone (10, 25, 50, 100, 250, 500, 1 000, 2 500, 5 000, 10 000 credits) so your `CREATE RESOURCE MONITOR` statements use human-readable numbers.

Each recommendation includes:

| Field | Description |
|-------|-------------|
| `avg_daily_credits` | Simple mean over the history window |
| `p95_daily_credits` | 95th-percentile daily usage — resists outlier days |
| `recommended_quota` | Rounded monthly quota |
| `recommended_cost_usd` | Estimated monthly cost at your `credits_per_dollar` rate |
| `quota_status` | `uncovered`, `undersized`, `oversized`, or `adequate` |
| `priority` | `high`, `medium`, or `low` (based on spend level and volatility) |

**`quota_status` thresholds:**

| Status | Condition |
|--------|-----------|
| `uncovered` | No existing monitor for this warehouse |
| `undersized` | Current quota is less than 77 % of recommended |
| `oversized` | Current quota is more than 143 % of recommended |
| `adequate` | Current quota is within ±30 % of recommended |

### Tuning the analysis

You can adjust two query parameters:

- `history_days` (7–90, default 30) — use fewer days for faster-changing workloads
- `buffer_pct` (0–1.0, default 0.20) — increase the buffer if you have highly variable workloads

---

## Generating DDL

Click **Generate SQL** next to any recommendation (or call `GET /api/resource-monitors/generate-sql?warehouse=MY_WH`) to get a complete `CREATE OR REPLACE RESOURCE MONITOR` statement:

```sql
-- Resource monitor for TRANSFORM_WH
-- Based on 30 days of history
-- Avg daily credits: 0.85  |  P95 daily: 1.42  |  Est. monthly cost: $16.67
CREATE OR REPLACE RESOURCE MONITOR RM_TRANSFORM_WH
    WITH CREDIT_QUOTA = 50            -- MONTHLY credit limit
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY
    TRIGGERS
        ON 75  PERCENT DO NOTIFY    -- email account admins
        ON 100  PERCENT DO SUSPEND  -- suspend all warehouses on this monitor
        ON 110 PERCENT DO SUSPEND_IMMEDIATE;

-- Assign the monitor to the warehouse
ALTER WAREHOUSE TRANSFORM_WH SET RESOURCE_MONITOR = RM_TRANSFORM_WH;
```

Copy the statement into a Snowflake worksheet and run it as a user with the `CREATE RESOURCE MONITOR` privilege (typically `ACCOUNTADMIN` or `SYSADMIN`).

---

## Proximity alerts

The **Proximity Alerts** tab shows which monitors are approaching their credit limits so you can act before workloads are unexpectedly suspended.

| Severity | Condition |
|----------|-----------|
| 🔴 **Critical** | Within 5 percentage points of a trigger threshold |
| 🟠 **High** | Within 15 percentage points of a trigger threshold |
| 🟡 **Medium** | Trigger is ahead but more than 15 pp away |

Alerts are computed from the last synced `used_credits / credit_quota` ratio — run a fresh sync to get up-to-date values.

---

## Per-user and per-role budgets

FrostWatch can track credit spend against configurable daily limits for individual users and roles. Configure them in `config.yaml`:

```yaml
user_credit_budgets:
  ANALYST_ALICE: 5.0    # daily credit limit
  DBT_SVC: 50.0
  ML_TEAM_SVC: 20.0

role_credit_budgets:
  ANALYST: 15.0
  TRANSFORMER: 10.0
```

The **Budgets** tab (or `GET /api/resource-monitors/budgets?days=7`) shows:

- Credits consumed in the selected window
- Daily budget and period budget (daily × days)
- Percentage of budget used
- Whether the entity is over-budget for the period

!!! note
    Budget tracking uses the `CachedQuery` data already fetched during sync — it does not require any additional Snowflake permissions beyond what FrostWatch already uses.

---

## Required Snowflake permissions

To sync existing resource monitors FrostWatch needs:

```sql
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <frostwatch_role>;
```

This permission is already needed for query history and warehouse metering. No additional permissions are required for reading `RESOURCE_MONITORS`.

To *apply* the generated DDL in Snowflake:

```sql
GRANT CREATE RESOURCE MONITOR ON ACCOUNT TO ROLE SYSADMIN;
```

FrostWatch never applies DDL automatically — it only generates SQL for you to review and run.
