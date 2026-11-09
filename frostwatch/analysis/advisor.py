"""Savings Advisor: rule-based Snowflake cost checks with dollar estimates and fix SQL.

Works without an LLM. Each check reads a small amount of ACCOUNT_USAGE data and
returns ``Finding`` objects that carry an estimated monthly saving, the evidence
behind it, and copy-paste SQL to apply the fix.

Pipeline: ``collect_inputs`` (Snowflake I/O, each query isolated so a missing
privilege only skips one check) -> ``analyze`` (pure, unit-tested) -> render.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

Severity = Literal["high", "medium", "low", "info"]
Category = Literal["compute", "storage", "cloud_services", "governance", "performance"]

GB = 1024**3
TB = 1024**4

# Credits per hour for a standard warehouse, per cluster.
SIZE_CREDITS_PER_HOUR: dict[str, float] = {
    "XSMALL": 1,
    "SMALL": 2,
    "MEDIUM": 4,
    "LARGE": 8,
    "XLARGE": 16,
    "2XLARGE": 32,
    "3XLARGE": 64,
    "4XLARGE": 128,
    "5XLARGE": 256,
    "6XLARGE": 512,
}
SIZE_ORDER = list(SIZE_CREDITS_PER_HOUR)
# Names accepted by ALTER WAREHOUSE ... SET WAREHOUSE_SIZE.
SQL_SIZE_NAME = {
    "2XLARGE": "XXLARGE",
    "3XLARGE": "XXXLARGE",
    "4XLARGE": "X4LARGE",
    "5XLARGE": "X5LARGE",
    "6XLARGE": "X6LARGE",
}

# Snowflake bills a minimum of 60 seconds each time a warehouse resumes, so an
# auto-suspend of 60s is the usual sweet spot.
RECOMMENDED_AUTO_SUSPEND_S = 60

DOCS = {
    "auto_suspend": "https://docs.snowflake.com/en/user-guide/warehouses-considerations",
    "oversized": "https://docs.snowflake.com/en/user-guide/warehouses-considerations",
    "spilling": "https://docs.snowflake.com/en/user-guide/performance-query-warehouse-memory",
    "queuing": "https://docs.snowflake.com/en/user-guide/warehouses-multicluster",
    "result_cache": "https://docs.snowflake.com/en/user-guide/querying-persisted-results",
    "cloud_services": "https://docs.snowflake.com/en/user-guide/cost-understanding-compute",
    "time_travel": "https://docs.snowflake.com/en/user-guide/data-cdp-storage-costs",
    "unused_tables": "https://docs.snowflake.com/en/sql-reference/account-usage/access_history",
    "no_monitor": "https://docs.snowflake.com/en/user-guide/resource-monitors",
    "clustering": "https://docs.snowflake.com/en/user-guide/tables-auto-reclustering",
}


# ── SQL ──────────────────────────────────────────────────────────────────────
# All queries are read-only and parameterised on %(days)s. Keep literal percent
# signs out of these strings (pyformat would treat them as placeholders).

SQL: dict[str, str] = {
    "warehouses": "SHOW WAREHOUSES",
    "metering": """
SELECT warehouse_name,
       SUM(credits_used) AS credits,
       COUNT(DISTINCT DATE_TRUNC('hour', start_time)) AS active_hours
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -%(days)s, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
""",
    "resumes": """
SELECT warehouse_name, COUNT(*) AS resumes
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
WHERE timestamp >= DATEADD('day', -%(days)s, CURRENT_TIMESTAMP())
  AND event_name = 'RESUME_WAREHOUSE'
  AND event_state = 'COMPLETED'
GROUP BY warehouse_name
""",
    "wh_stats": """
SELECT warehouse_name,
       ANY_VALUE(warehouse_size) AS warehouse_size,
       COUNT(*) AS queries,
       APPROX_PERCENTILE(execution_time, 0.95) / 1000 AS p95_exec_s,
       APPROX_PERCENTILE(bytes_scanned, 0.95) AS p95_bytes_scanned,
       SUM(bytes_spilled_to_local_storage) AS spill_local_bytes,
       SUM(bytes_spilled_to_remote_storage) AS spill_remote_bytes,
       SUM(queued_overload_time) / 1000 AS queued_s,
       SUM(execution_time) / 1000 AS exec_s
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -%(days)s, CURRENT_TIMESTAMP())
  AND warehouse_name IS NOT NULL
  AND execution_status = 'SUCCESS'
GROUP BY warehouse_name
""",
    "repeated": """
SELECT query_hash,
       ANY_VALUE(warehouse_name) AS warehouse_name,
       ANY_VALUE(warehouse_size) AS warehouse_size,
       ANY_VALUE(LEFT(query_text, 400)) AS sample_text,
       COUNT(*) AS runs,
       SUM(execution_time) / 1000 AS exec_s
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -%(days)s, CURRENT_TIMESTAMP())
  AND query_type = 'SELECT'
  AND execution_status = 'SUCCESS'
  AND bytes_scanned > 0
  AND execution_time > 1000
  AND query_hash IS NOT NULL
GROUP BY query_hash
HAVING COUNT(*) >= 20
ORDER BY exec_s DESC
LIMIT 10
""",
    "cloud_services": """
SELECT SUM(credits_used_compute) AS compute_credits,
       SUM(credits_used_cloud_services) AS cloud_services_credits,
       SUM(credits_adjustment_cloud_services) AS cloud_services_adjustment,
       SUM(credits_billed) AS credits_billed
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE usage_date >= DATEADD('day', -%(days)s, CURRENT_DATE())
""",
    "time_travel": """
SELECT table_catalog, table_schema, table_name,
       active_bytes, time_travel_bytes, failsafe_bytes, is_transient
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
WHERE deleted = FALSE
  AND (time_travel_bytes + failsafe_bytes) > 50 * POWER(1024, 3)
  AND (time_travel_bytes + failsafe_bytes) > active_bytes
ORDER BY time_travel_bytes + failsafe_bytes DESC
LIMIT 15
""",
    "unused_tables": """
WITH accessed AS (
    SELECT DISTINCT UPPER(f.value:"objectName"::STRING) AS fqn
    FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
         LATERAL FLATTEN(input => base_objects_accessed) f
    WHERE query_start_time >= DATEADD('day', -90, CURRENT_TIMESTAMP())
)
SELECT t.table_catalog, t.table_schema, t.table_name, t.active_bytes
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS t
LEFT JOIN accessed a
  ON a.fqn = UPPER(t.table_catalog || '.' || t.table_schema || '.' || t.table_name)
WHERE t.deleted = FALSE
  AND a.fqn IS NULL
  AND t.active_bytes > 100 * POWER(1024, 3)
  AND t.table_created < DATEADD('day', -90, CURRENT_TIMESTAMP())
  AND t.table_catalog <> 'SNOWFLAKE'
ORDER BY t.active_bytes DESC
LIMIT 15
""",
    "clustering": """
SELECT database_name, schema_name, table_name, SUM(credits_used) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
WHERE start_time >= DATEADD('day', -%(days)s, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY credits DESC
LIMIT 10
""",
}

# Why a dataset may be unavailable, shown in the report when a query fails.
SKIP_HINTS = {
    "unused_tables": "ACCESS_HISTORY needs Enterprise Edition or higher",
    "resumes": "falls back to active hours from metering",
}


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class Finding:
    check_id: str
    title: str
    category: Category
    severity: Severity
    object_name: str
    monthly_savings_usd: float
    evidence: str
    recommendation: str
    fix_sql: str = ""
    monthly_cost_usd: float = 0.0
    docs_url: str = ""


@dataclass
class AuditInputs:
    warehouses: list[dict] = field(default_factory=list)
    metering: list[dict] = field(default_factory=list)
    resumes: list[dict] = field(default_factory=list)
    wh_stats: list[dict] = field(default_factory=list)
    repeated: list[dict] = field(default_factory=list)
    cloud_services: list[dict] = field(default_factory=list)
    time_travel: list[dict] = field(default_factory=list)
    unused_tables: list[dict] = field(default_factory=list)
    clustering: list[dict] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


@dataclass
class AuditResult:
    generated_at: str
    account: str
    days: int
    credit_price_usd: float
    storage_price_per_tb_usd: float
    monthly_compute_spend_usd: float
    monthly_savings_usd: float
    findings: list[Finding]
    skipped: dict[str, str]
    demo: bool = False

    @property
    def annual_savings_usd(self) -> float:
        return self.monthly_savings_usd * 12

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["annual_savings_usd"] = round(self.annual_savings_usd, 2)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AuditResult:
        d = dict(d)
        d.pop("annual_savings_usd", None)
        d["findings"] = [Finding(**f) for f in d.get("findings", [])]
        return cls(**d)


# ── Helpers ──────────────────────────────────────────────────────────────────


def normalize_size(size: str | None) -> str:
    """'X-Small' / 'XSMALL' / 'X-Large' / '2X-Large' -> canonical key."""
    if not size:
        return ""
    key = size.upper().replace("-", "").replace("_", "").replace(" ", "")
    return {"XXLARGE": "2XLARGE", "XXXLARGE": "3XLARGE"}.get(key, key)


def credits_per_hour(size: str | None) -> float:
    return SIZE_CREDITS_PER_HOUR.get(normalize_size(size), 0.0)


def next_size_down(size: str | None) -> str | None:
    key = normalize_size(size)
    if key not in SIZE_ORDER or SIZE_ORDER.index(key) == 0:
        return None
    return SIZE_ORDER[SIZE_ORDER.index(key) - 1]


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _f(row: dict, key: str, default: float = 0.0) -> float:
    v = row.get(key)
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _severity(monthly_usd: float) -> Severity:
    if monthly_usd >= 500:
        return "high"
    if monthly_usd >= 100:
        return "medium"
    return "low"


def _money(v: float) -> str:
    return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"


def _lower_keys(rows: list[dict]) -> list[dict]:
    return [{str(k).lower(): v for k, v in r.items()} for r in rows]


# ── Checks ───────────────────────────────────────────────────────────────────


def check_auto_suspend(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    resumes = {r["warehouse_name"]: _f(r, "resumes") for r in inp.resumes}
    metering = {r["warehouse_name"]: r for r in inp.metering}
    out: list[Finding] = []
    for wh in inp.warehouses:
        name = str(wh.get("name", ""))
        rate = credits_per_hour(wh.get("size"))
        if not name or not rate:
            continue
        raw = wh.get("auto_suspend")
        suspend_s = None if raw in (None, "", "null") else _f(wh, "auto_suspend")
        m = metering.get(name, {})
        active_hours = _f(m, "active_hours")
        if suspend_s is None or suspend_s == 0:
            # Never suspends: everything outside active hours is idle burn,
            # but it only matters if the warehouse is actually running.
            if not m:
                continue
            # A never-suspending warehouse is billed nearly every hour.
            period_hours = 24 * _days_from_scale(scale)
            if active_hours < 0.8 * period_hours:
                continue
            monthly_cost = _f(m, "credits") * price * scale
            saving = monthly_cost * 0.5
            out.append(
                Finding(
                    check_id="auto_suspend_disabled",
                    title="Warehouse never suspends",
                    category="compute",
                    severity="high",
                    object_name=name,
                    monthly_savings_usd=round(saving, 2),
                    monthly_cost_usd=round(monthly_cost, 2),
                    evidence=f"AUTO_SUSPEND is off and the warehouse was billed in "
                    f"{active_hours:.0f} hourly slots, nearly around the clock.",
                    recommendation="Enable auto-suspend so the warehouse stops billing when idle. "
                    "Savings assume roughly half of its running hours are idle.",
                    fix_sql=f"ALTER WAREHOUSE {quote_ident(name)} SET AUTO_SUSPEND = "
                    f"{RECOMMENDED_AUTO_SUSPEND_S};",
                    docs_url=DOCS["auto_suspend"],
                )
            )
            continue
        if suspend_s <= RECOMMENDED_AUTO_SUSPEND_S:
            continue
        clusters = max(1.0, _f(wh, "min_cluster_count", 1.0))
        n_resumes = resumes.get(name)
        if n_resumes is None:
            # Without event history, assume one idle tail per active hour block.
            n_resumes = active_hours / 2
        idle_s = (suspend_s - RECOMMENDED_AUTO_SUSPEND_S) * n_resumes
        saving = idle_s / 3600 * rate * clusters * price * scale
        if saving < 5:
            continue
        out.append(
            Finding(
                check_id="auto_suspend_high",
                title="Auto-suspend set too high",
                category="compute",
                severity=_severity(saving),
                object_name=name,
                monthly_savings_usd=round(saving, 2),
                monthly_cost_usd=round(_f(m, "credits") * price * scale, 2),
                evidence=f"AUTO_SUSPEND = {suspend_s:.0f}s on a {wh.get('size')} warehouse "
                f"that resumed ~{n_resumes:.0f} times. Each resume burns up to "
                f"{suspend_s - RECOMMENDED_AUTO_SUSPEND_S:.0f}s of idle time before suspending.",
                recommendation=f"Lower AUTO_SUSPEND to {RECOMMENDED_AUTO_SUSPEND_S}s. Keep it "
                "higher only for BI warehouses that depend on a warm local cache.",
                fix_sql=f"ALTER WAREHOUSE {quote_ident(name)} SET AUTO_SUSPEND = "
                f"{RECOMMENDED_AUTO_SUSPEND_S};",
                docs_url=DOCS["auto_suspend"],
            )
        )
    return out


def _days_from_scale(scale: float) -> float:
    return 30.0 / scale if scale else 30.0


def check_warehouse_sizing(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    sizes = {str(w.get("name")): w.get("size") for w in inp.warehouses}
    metering = {r["warehouse_name"]: _f(r, "credits") for r in inp.metering}
    out: list[Finding] = []
    for s in inp.wh_stats:
        name = s["warehouse_name"]
        size = sizes.get(name) or s.get("warehouse_size")
        queries = _f(s, "queries")
        exec_s = _f(s, "exec_s")
        spill_remote = _f(s, "spill_remote_bytes")
        spill_local = _f(s, "spill_local_bytes")
        monthly_cost = metering.get(name, 0.0) * price * scale

        # Oversized: Medium or bigger, only small fast queries, no spilling.
        smaller = next_size_down(size)
        if (
            smaller
            and credits_per_hour(size) >= 4
            and queries >= 100
            and _f(s, "p95_exec_s") < 10
            and _f(s, "p95_bytes_scanned") < 1 * GB
            and spill_remote == 0
            and spill_local < 1 * GB
            and monthly_cost > 0
        ):
            saving = monthly_cost * 0.3
            out.append(
                Finding(
                    check_id="oversized_warehouse",
                    title="Warehouse looks oversized",
                    category="compute",
                    severity=_severity(saving),
                    object_name=name,
                    monthly_savings_usd=round(saving, 2),
                    monthly_cost_usd=round(monthly_cost, 2),
                    evidence=f"{queries:,.0f} queries on a {size} warehouse: p95 runtime "
                    f"{_f(s, 'p95_exec_s'):.1f}s, p95 scan "
                    f"{_f(s, 'p95_bytes_scanned') / GB * 1024:,.0f} MB, no spilling.",
                    recommendation=f"Try one size down ({smaller}) for a week and compare "
                    "runtimes. Small queries rarely get slower, so cost drops close to half; "
                    "the estimate assumes 30 percent to stay conservative.",
                    fix_sql=f"ALTER WAREHOUSE {quote_ident(name)} SET WAREHOUSE_SIZE = "
                    f"'{SQL_SIZE_NAME.get(smaller, smaller)}';",
                    docs_url=DOCS["oversized"],
                )
            )

        if spill_remote > 10 * GB:
            out.append(
                Finding(
                    check_id="remote_spilling",
                    title="Queries spilling to remote storage",
                    category="performance",
                    severity="medium",
                    object_name=name,
                    monthly_savings_usd=0.0,
                    monthly_cost_usd=round(monthly_cost, 2),
                    evidence=f"{spill_remote / GB:,.0f} GB spilled to remote storage. Remote "
                    "spilling can make queries many times slower, and slow queries cost credits.",
                    recommendation="Find the spilling queries (BYTES_SPILLED_TO_REMOTE_STORAGE "
                    "in QUERY_HISTORY). Reduce the data they process, or move just those "
                    "jobs to a larger warehouse.",
                    fix_sql="SELECT query_id, LEFT(query_text, 200), "
                    "bytes_spilled_to_remote_storage\nFROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY\n"
                    f"WHERE warehouse_name = '{name}' AND bytes_spilled_to_remote_storage > 0\n"
                    "ORDER BY bytes_spilled_to_remote_storage DESC LIMIT 20;",
                    docs_url=DOCS["spilling"],
                )
            )

        queued = _f(s, "queued_s")
        if exec_s > 3600 and queued > 0.1 * exec_s:
            out.append(
                Finding(
                    check_id="queuing",
                    title="Queries waiting in queue",
                    category="performance",
                    severity="low",
                    object_name=name,
                    monthly_savings_usd=0.0,
                    monthly_cost_usd=round(monthly_cost, 2),
                    evidence=f"Queries spent {queued / 3600:,.1f}h queued vs "
                    f"{exec_s / 3600:,.1f}h executing ({queued / exec_s:.0%}).",
                    recommendation="Concurrency, not size, is the bottleneck. Use a "
                    "multi-cluster warehouse (Enterprise) with a low MAX_CLUSTER_COUNT, or "
                    "split workloads onto separate warehouses. Upsizing would overpay.",
                    fix_sql=f"ALTER WAREHOUSE {quote_ident(name)} SET MIN_CLUSTER_COUNT = 1 "
                    "MAX_CLUSTER_COUNT = 3 SCALING_POLICY = 'ECONOMY';",
                    docs_url=DOCS["queuing"],
                )
            )
    return out


def check_repeated_queries(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    out: list[Finding] = []
    for r in inp.repeated[:5]:
        rate = credits_per_hour(r.get("warehouse_size")) or 1.0
        # Upper bound: assumes each query had the warehouse to itself.
        monthly_cost = _f(r, "exec_s") / 3600 * rate * price * scale
        saving = monthly_cost * 0.5
        if saving < 10:
            continue
        runs = _f(r, "runs")
        sample = " ".join(str(r.get("sample_text") or "").split())[:160]
        out.append(
            Finding(
                check_id="repeated_query",
                title="Identical query re-runs without hitting the result cache",
                category="compute",
                severity=_severity(saving),
                object_name=f"{r.get('warehouse_name')} / {str(r.get('query_hash'))[:12]}",
                monthly_savings_usd=round(saving, 2),
                monthly_cost_usd=round(monthly_cost, 2),
                evidence=f"Ran {runs:,.0f} times with identical text and still scanned data "
                f"each time. Sample: {sample}",
                recommendation="Common causes: CURRENT_TIMESTAMP() or RANDOM() in the SQL, "
                "USE_CACHED_RESULT = FALSE on the session, or the source table changes "
                "between runs. Remove non-deterministic functions, or materialize the "
                "result (dynamic table or scheduled table) for dashboards.",
                fix_sql="SHOW PARAMETERS LIKE 'USE_CACHED_RESULT' IN ACCOUNT;",
                docs_url=DOCS["result_cache"],
            )
        )
    return out


def check_cloud_services(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    if not inp.cloud_services:
        return []
    r = inp.cloud_services[0]
    cs = _f(r, "cloud_services_credits")
    adj = _f(r, "cloud_services_adjustment")
    billed = cs + adj  # adjustment is negative
    if billed <= 0:
        return []
    monthly_billed = billed * price * scale
    if monthly_billed < 10:
        return []
    compute = _f(r, "compute_credits")
    ratio = cs / compute if compute else 0
    saving = monthly_billed * 0.5
    return [
        Finding(
            check_id="cloud_services_billed",
            title="Paying for cloud services above the free 10 percent",
            category="cloud_services",
            severity=_severity(saving),
            object_name="ACCOUNT",
            monthly_savings_usd=round(saving, 2),
            monthly_cost_usd=round(monthly_billed, 2),
            evidence=f"Cloud services used {cs:,.1f} credits ({ratio:.0%} of compute); "
            f"{billed:,.1f} credits were billed after the daily adjustment.",
            recommendation="Usually caused by very frequent tiny queries, heavy SHOW / "
            "metadata calls from tools, or complex compilation. Find the top query types by "
            "CREDITS_USED_CLOUD_SERVICES and batch or cache them.",
            fix_sql="SELECT query_type, warehouse_name, COUNT(*) AS n,\n"
            "       SUM(credits_used_cloud_services) AS cs_credits\n"
            "FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY\n"
            "WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())\n"
            "GROUP BY 1, 2 ORDER BY cs_credits DESC LIMIT 20;",
            docs_url=DOCS["cloud_services"],
        )
    ]


def _fqn(r: dict, db: str = "table_catalog", sc: str = "table_schema", t: str = "table_name"):
    return ".".join(quote_ident(str(r.get(k, ""))) for k in (db, sc, t))


def check_time_travel(inp: AuditInputs, storage_price: float) -> list[Finding]:
    out: list[Finding] = []
    for r in inp.time_travel:
        tt = _f(r, "time_travel_bytes")
        fs = _f(r, "failsafe_bytes")
        active = _f(r, "active_bytes")
        transient = str(r.get("is_transient", "")).upper() in ("YES", "TRUE")
        # Transient tables have no fail-safe; retention 1 day cuts most time travel.
        saving = (fs + tt * 0.8) / TB * storage_price
        if saving < 5:
            continue
        fqn = _fqn(r)
        out.append(
            Finding(
                check_id="time_travel_storage",
                title="Time Travel and Fail-safe bigger than the table",
                category="storage",
                severity=_severity(saving),
                object_name=fqn,
                monthly_savings_usd=round(saving, 2),
                monthly_cost_usd=round((tt + fs + active) / TB * storage_price, 2),
                evidence=f"Active {active / GB:,.0f} GB, Time Travel {tt / GB:,.0f} GB, "
                f"Fail-safe {fs / GB:,.0f} GB. A high-churn table (full reloads or heavy "
                "updates) keeps paying for every old version.",
                recommendation="If the table can be rebuilt from source, make it TRANSIENT "
                "(no Fail-safe) and cut retention to 0 or 1 day. For dbt models use "
                "`+transient: true`."
                if not transient
                else "Cut DATA_RETENTION_TIME_IN_DAYS to 0 or 1 day.",
                fix_sql=f"ALTER TABLE {fqn} SET DATA_RETENTION_TIME_IN_DAYS = 1;",
                docs_url=DOCS["time_travel"],
            )
        )
    return out


def check_unused_tables(inp: AuditInputs, storage_price: float) -> list[Finding]:
    out: list[Finding] = []
    for r in inp.unused_tables:
        active = _f(r, "active_bytes")
        saving = active / TB * storage_price
        if saving < 5:
            continue
        fqn = _fqn(r)
        out.append(
            Finding(
                check_id="unused_table",
                title="Large table not read in 90 days",
                category="storage",
                severity=_severity(saving),
                object_name=fqn,
                monthly_savings_usd=round(saving, 2),
                monthly_cost_usd=round(saving, 2),
                evidence=f"{active / GB:,.0f} GB of active storage with no reads in "
                "ACCESS_HISTORY for 90 days.",
                recommendation="Confirm with the owner, then drop it or unload it to cheap "
                "object storage. The DROP is commented out on purpose.",
                fix_sql=f"-- DROP TABLE {fqn};",
                docs_url=DOCS["unused_tables"],
            )
        )
    return out


def check_resource_monitors(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    metering = {r["warehouse_name"]: _f(r, "credits") for r in inp.metering}
    unguarded = []
    for wh in inp.warehouses:
        mon = wh.get("resource_monitor")
        if mon in (None, "", "null", "NULL"):
            name = str(wh.get("name"))
            monthly_credits = metering.get(name, 0.0) * scale
            if monthly_credits > 0:
                unguarded.append((name, monthly_credits))
    if not unguarded:
        return []
    unguarded.sort(key=lambda x: -x[1])
    sql_lines = []
    for name, credits in unguarded[:10]:
        quota = max(10, int(round(credits * 1.5, -1)))
        mon = quote_ident(f"FW_{name}_MONTHLY"[:255])
        sql_lines.append(
            f"CREATE RESOURCE MONITOR {mon} WITH CREDIT_QUOTA = {quota} FREQUENCY = MONTHLY "
            "START_TIMESTAMP = IMMEDIATELY\n  TRIGGERS ON 80 PERCENT DO NOTIFY "
            "ON 100 PERCENT DO SUSPEND ON 120 PERCENT DO SUSPEND_IMMEDIATE;\n"
            f"ALTER WAREHOUSE {quote_ident(name)} SET RESOURCE_MONITOR = {mon};"
        )
    total = sum(c for _, c in unguarded) * price
    return [
        Finding(
            check_id="no_resource_monitor",
            title="Warehouses with no spending cap",
            category="governance",
            severity="medium" if total >= 1000 else "low",
            object_name=", ".join(n for n, _ in unguarded[:5])
            + (f" (+{len(unguarded) - 5} more)" if len(unguarded) > 5 else ""),
            monthly_savings_usd=0.0,
            monthly_cost_usd=round(total, 2),
            evidence=f"{len(unguarded)} warehouse(s) spending {_money(total)}/month have no "
            "resource monitor. A runaway query or a forgotten loop has no ceiling.",
            recommendation="Add a monthly monitor per warehouse at about 1.5x normal usage: "
            "notify at 80 percent, suspend at 100 percent. Requires ACCOUNTADMIN.",
            fix_sql="\n".join(sql_lines),
            docs_url=DOCS["no_monitor"],
        )
    ]


def check_clustering(inp: AuditInputs, price: float, scale: float) -> list[Finding]:
    out: list[Finding] = []
    for r in inp.clustering:
        monthly_cost = _f(r, "credits") * price * scale
        if monthly_cost < 100:
            continue
        fqn = _fqn(r, "database_name", "schema_name", "table_name")
        out.append(
            Finding(
                check_id="auto_clustering_cost",
                title="Expensive automatic clustering",
                category="compute",
                severity="info",
                object_name=fqn,
                monthly_savings_usd=0.0,
                monthly_cost_usd=round(monthly_cost, 2),
                evidence=f"Automatic clustering costs about {_money(monthly_cost)}/month on "
                "this table.",
                recommendation="Check that queries actually filter on the clustering key and "
                "that the table is not rewritten constantly. If pruning did not improve, "
                "suspend reclustering or pick a lower-cardinality key.",
                fix_sql=f"SELECT SYSTEM$CLUSTERING_INFORMATION('{fqn}');\n"
                f"-- ALTER TABLE {fqn} SUSPEND RECLUSTER;",
                docs_url=DOCS["clustering"],
            )
        )
    return out


# ── Orchestration ────────────────────────────────────────────────────────────

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}


def analyze(
    inp: AuditInputs,
    *,
    days: int = 30,
    credit_price: float = 3.0,
    storage_price_per_tb: float = 23.0,
    account: str = "",
    demo: bool = False,
) -> AuditResult:
    """Run every check over collected inputs. Pure: no I/O."""
    inp.metering = _lower_keys(inp.metering)
    inp.warehouses = _lower_keys(inp.warehouses)
    for attr in (
        "resumes",
        "wh_stats",
        "repeated",
        "cloud_services",
        "time_travel",
        "unused_tables",
        "clustering",
    ):
        setattr(inp, attr, _lower_keys(getattr(inp, attr)))

    scale = 30.0 / days if days else 1.0
    findings: list[Finding] = []
    findings += check_auto_suspend(inp, credit_price, scale)
    findings += check_warehouse_sizing(inp, credit_price, scale)
    findings += check_repeated_queries(inp, credit_price, scale)
    findings += check_cloud_services(inp, credit_price, scale)
    findings += check_time_travel(inp, storage_price_per_tb)
    findings += check_unused_tables(inp, storage_price_per_tb)
    findings += check_resource_monitors(inp, credit_price, scale)
    findings += check_clustering(inp, credit_price, scale)

    # A warehouse that never suspends and is oversized should not double count:
    # cap total savings per warehouse at 70 percent of its monthly cost.
    per_object: dict[str, float] = {}
    for f in findings:
        if f.category == "compute" and f.monthly_cost_usd:
            cap = f.monthly_cost_usd * 0.7
            used = per_object.get(f.object_name, 0.0)
            allowed = max(0.0, cap - used)
            if f.monthly_savings_usd > allowed:
                f.monthly_savings_usd = round(allowed, 2)
            per_object[f.object_name] = used + f.monthly_savings_usd

    findings.sort(key=lambda f: (-f.monthly_savings_usd, _SEVERITY_RANK[f.severity]))

    compute_spend = sum(_f(r, "credits") for r in inp.metering) * credit_price * scale
    return AuditResult(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        account=account,
        days=days,
        credit_price_usd=credit_price,
        storage_price_per_tb_usd=storage_price_per_tb,
        monthly_compute_spend_usd=round(compute_spend, 2),
        monthly_savings_usd=round(sum(f.monthly_savings_usd for f in findings), 2),
        findings=findings,
        skipped=dict(inp.skipped),
        demo=demo,
    )


class _Executor(Protocol):
    async def execute(self, sql: str, params: dict | None = None) -> list[dict]: ...


async def collect_inputs(client: _Executor, days: int = 30, on_step=None) -> AuditInputs:
    """Run every audit query. A failing query (missing privilege, edition) only
    skips that dataset; its error is recorded in ``skipped``."""
    inp = AuditInputs()
    for key, sql in SQL.items():
        if on_step:
            on_step(key)
        try:
            rows = await client.execute(sql, {"days": int(days)} if "%(days)s" in sql else None)
            setattr(inp, key, _lower_keys(rows))
        except Exception as exc:  # noqa: BLE001 - surface any failure as a skip
            msg = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else repr(exc)
            hint = SKIP_HINTS.get(key)
            inp.skipped[key] = f"{msg} ({hint})" if hint else msg
        await asyncio.sleep(0)
    return inp


async def run_audit(client: _Executor, config: Any, days: int = 30, on_step=None) -> AuditResult:
    inp = await collect_inputs(client, days, on_step)
    return analyze(
        inp,
        days=days,
        credit_price=float(getattr(config, "credits_per_dollar", 3.0) or 3.0),
        storage_price_per_tb=float(getattr(config, "storage_price_per_tb", 23.0) or 23.0),
        account=str(getattr(config, "snowflake_account", "") or ""),
    )
