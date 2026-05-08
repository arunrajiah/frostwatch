"""Resource monitor analysis — recommendations, SQL generation, and proximity alerts.

Three public functions:

recommend_monitors(warehouse_metrics, existing_monitors, credits_per_dollar)
    Analyse per-warehouse daily spend and suggest new or updated resource monitors.

generate_monitor_sql(recommendation)
    Render a complete ``CREATE RESOURCE MONITOR`` DDL statement from a recommendation.

detect_proximity_alerts(monitors)
    Return monitors whose current ``used_credits / credit_quota`` ratio is close to
    a trigger threshold (notify / suspend / suspend-immediately).
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

# Proximity severity bands (used_pct relative to the relevant trigger %)
_PROXIMITY_CRITICAL_MARGIN = 5.0  # within 5 pp of the trigger
_PROXIMITY_HIGH_MARGIN = 15.0  # within 15 pp of the trigger


# ── Recommendation engine ─────────────────────────────────────────────────────


def recommend_monitors(
    warehouse_metrics: list[dict],
    existing_monitors: list[dict] | None = None,
    credits_per_dollar: float = 3.0,
    history_days: int = 30,
    buffer_pct: float = 0.20,
) -> list[dict]:
    """Generate resource monitor recommendations for each warehouse.

    Args:
        warehouse_metrics:  CachedWarehouseMetric dicts (warehouse_name, date,
                            credits_used, cost_usd).
        existing_monitors:  ResourceMonitor dicts already synced from Snowflake.
                            Used to mark whether a monitor already exists and
                            whether its quota looks under/over-sized.
        credits_per_dollar: Conversion factor for USD cost estimates.
        history_days:       How many days of history to use for averages.
        buffer_pct:         Fractional overhead added on top of the rolling
                            average when computing the recommended quota
                            (default 20 %).

    Returns:
        List of recommendation dicts sorted by ``monthly_credits_p95`` descending.
    """
    existing_monitors = existing_monitors or []
    cutoff = datetime.now(UTC).date() - timedelta(days=history_days)

    # Group daily credits by warehouse
    wh_days: dict[str, list[float]] = defaultdict(list)
    for m in warehouse_metrics:
        d = m.get("date")
        if isinstance(d, datetime):
            d = d.date()
        elif isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        if d and d >= cutoff:
            wh_days[str(m.get("warehouse_name") or "")].append(float(m.get("credits_used") or 0))

    # Build a lookup of warehouses already covered by a monitor
    monitored_whs: dict[str, str] = {}  # warehouse_name → monitor_name
    for mon in existing_monitors:
        wh_list_raw = mon.get("warehouses") or "[]"
        try:
            import json

            wh_list = json.loads(wh_list_raw) if isinstance(wh_list_raw, str) else wh_list_raw
        except Exception:
            wh_list = []
        for wh in wh_list:
            monitored_whs[str(wh)] = str(mon.get("name") or "")

    recommendations = []
    for wh_name, daily_credits in wh_days.items():
        if not wh_name or not daily_credits:
            continue

        n = len(daily_credits)
        avg = statistics.mean(daily_credits)
        stddev = statistics.stdev(daily_credits) if n > 1 else 0.0
        p95 = _percentile(daily_credits, 95)

        # Monthly quota = p95 × 30 days + buffer
        monthly_quota = math.ceil(p95 * 30 * (1 + buffer_pct))
        # Round up to a clean number
        monthly_quota = _round_up_quota(monthly_quota)

        cost_usd = monthly_quota / credits_per_dollar if credits_per_dollar else 0.0

        existing_monitor = monitored_whs.get(wh_name)
        current_quota: float | None = None
        quota_status = "uncovered"
        if existing_monitor:
            mon = next((m for m in existing_monitors if m.get("name") == existing_monitor), None)
            if mon and mon.get("credit_quota"):
                current_quota = float(mon["credit_quota"])
                ratio = monthly_quota / current_quota
                if ratio > 1.3:
                    quota_status = "undersized"
                elif ratio < 0.7:
                    quota_status = "oversized"
                else:
                    quota_status = "adequate"

        # Volatility band
        cv = stddev / avg if avg > 0 else 0.0  # coefficient of variation
        if cv > 0.5 or avg > 5.0:
            priority = "high"
        elif avg > 1.0:
            priority = "medium"
        else:
            priority = "low"

        recommendations.append(
            {
                "warehouse_name": wh_name,
                "avg_daily_credits": round(avg, 4),
                "p95_daily_credits": round(p95, 4),
                "monthly_credits_p95": round(p95 * 30, 2),
                "recommended_quota": monthly_quota,
                "recommended_cost_usd": round(cost_usd, 2),
                "frequency": "MONTHLY",
                "notify_at_percentage": 75.0,
                "suspend_at_percentage": 100.0,
                "suspend_immediately_at_percentage": 110.0,
                "existing_monitor": existing_monitor,
                "current_quota": current_quota,
                "quota_status": quota_status,
                "priority": priority,
                "history_days_used": n,
            }
        )

    recommendations.sort(key=lambda x: x["monthly_credits_p95"], reverse=True)
    return recommendations


# ── SQL generation ────────────────────────────────────────────────────────────


def generate_monitor_sql(recommendation: dict) -> str:
    """Render a ``CREATE OR REPLACE RESOURCE MONITOR`` DDL statement.

    The generated SQL is ready to copy-paste into a Snowflake worksheet.
    It includes inline comments explaining each clause.
    """
    wh = recommendation["warehouse_name"]
    quota = recommendation["recommended_quota"]
    freq = recommendation.get("frequency", "MONTHLY")
    notify = recommendation.get("notify_at_percentage", 75.0)
    suspend = recommendation.get("suspend_at_percentage", 100.0)
    suspend_imm = recommendation.get("suspend_immediately_at_percentage", 110.0)
    cost = recommendation.get("recommended_cost_usd", 0.0)
    avg = recommendation.get("avg_daily_credits", 0.0)
    p95 = recommendation.get("p95_daily_credits", 0.0)

    monitor_name = f"RM_{wh.upper()}"

    lines = [
        f"-- Resource monitor for {wh}",
        f"-- Based on {recommendation.get('history_days_used', 30)} days of history",
        f"-- Avg daily credits: {avg:.2f}  |  P95 daily: {p95:.2f}  |  Est. monthly cost: ${cost:.2f}",
        f"CREATE OR REPLACE RESOURCE MONITOR {monitor_name}",
        f"    WITH CREDIT_QUOTA = {quota}            -- {freq} credit limit",
        f"    FREQUENCY = {freq}",
        "    START_TIMESTAMP = IMMEDIATELY",
        "    TRIGGERS",
        f"        ON {int(notify)}  PERCENT DO NOTIFY    -- email account admins",
        f"        ON {int(suspend)}  PERCENT DO SUSPEND  -- suspend all warehouses on this monitor",
        f"        ON {int(suspend_imm)} PERCENT DO SUSPEND_IMMEDIATE;",
        "",
        "-- Assign the monitor to the warehouse",
        f"ALTER WAREHOUSE {wh} SET RESOURCE_MONITOR = {monitor_name};",
    ]
    return "\n".join(lines)


# ── Proximity alerts ──────────────────────────────────────────────────────────


def detect_proximity_alerts(monitors: list[dict]) -> list[dict]:
    """Return monitors that are close to a trigger threshold.

    Considers notify, suspend, and suspend-immediately thresholds. The monitor
    with the highest used-credit percentage is reported first.

    Args:
        monitors: ResourceMonitor dicts (name, credit_quota, used_credits,
                  notify_at_percentage, suspend_at_percentage,
                  suspend_immediately_at_percentage).

    Returns:
        List of alert dicts sorted by ``used_pct`` descending.
    """
    alerts = []
    for m in monitors:
        quota = float(m.get("credit_quota") or 0)
        used = float(m.get("used_credits") or 0)
        if quota <= 0:
            continue

        used_pct = (used / quota) * 100.0

        # Find the nearest trigger threshold
        thresholds = []
        for pct, label in [
            (m.get("suspend_immediately_at_percentage"), "suspend_immediately"),
            (m.get("suspend_at_percentage"), "suspend"),
            (m.get("notify_at_percentage"), "notify"),
        ]:
            if pct is not None:
                thresholds.append((float(pct), label))

        nearest_trigger: str | None = None
        nearest_margin: float | None = None
        severity: str | None = None

        for trigger_pct, label in sorted(thresholds):
            if used_pct <= trigger_pct:
                margin = trigger_pct - used_pct
                if nearest_margin is None or margin < nearest_margin:
                    nearest_margin = margin
                    nearest_trigger = label
                    if margin <= _PROXIMITY_CRITICAL_MARGIN:
                        severity = "critical"
                    elif margin <= _PROXIMITY_HIGH_MARGIN:
                        severity = "high"
                    else:
                        severity = "medium"

        if severity is None:
            # Already past all thresholds
            severity = "critical"
            nearest_trigger = "exceeded"
            nearest_margin = 0.0

        remaining = float(m.get("remaining_credits") or max(0.0, quota - used))

        alerts.append(
            {
                "monitor_name": m.get("name"),
                "warehouse_names": m.get("warehouses") or "[]",
                "credit_quota": round(quota, 2),
                "used_credits": round(used, 4),
                "remaining_credits": round(remaining, 4),
                "used_pct": round(used_pct, 2),
                "nearest_trigger": nearest_trigger,
                "nearest_trigger_pct": (
                    next((p for p, lbl in thresholds if lbl == nearest_trigger), None)
                    if nearest_trigger != "exceeded"
                    else None
                ),
                "margin_to_trigger_ppt": (
                    round(nearest_margin, 2) if nearest_margin is not None else None
                ),
                "frequency": m.get("frequency"),
                "severity": severity,
            }
        )

    alerts.sort(key=lambda x: x["used_pct"], reverse=True)
    return alerts


# ── Budget tracking ───────────────────────────────────────────────────────────


def compute_budget_usage(
    queries: list[dict],
    user_budgets: dict[str, float],
    role_budgets: dict[str, float],
    days: int = 1,
) -> dict:
    """Compute per-user and per-role credit spend vs configured daily budgets.

    Args:
        queries:       CachedQuery dicts for the relevant time window.
        user_budgets:  {user_name: daily_credit_limit}
        role_budgets:  {role_name: daily_credit_limit}
        days:          Number of days the window covers (used to scale daily budgets).

    Returns:
        Dict with keys ``users`` and ``roles``, each a list of budget records.
    """
    user_credits: dict[str, float] = defaultdict(float)
    role_credits: dict[str, float] = defaultdict(float)

    for q in queries:
        user = str(q.get("user_name") or "")
        role = str(q.get("role_name") or "")
        credits = float(q.get("credits_used") or 0)
        if user:
            user_credits[user] += credits
        if role:
            role_credits[role] += credits

    def _make_records(credits_map: dict[str, float], budget_map: dict[str, float]) -> list[dict]:
        # Include all budgeted entities + any unbudgeted ones with spend
        all_names = set(budget_map) | set(credits_map)
        records = []
        for name in all_names:
            spent = round(credits_map.get(name, 0.0), 6)
            daily_budget = budget_map.get(name)
            period_budget = daily_budget * days if daily_budget is not None else None
            pct_used = round(spent / period_budget * 100, 1) if period_budget else None
            records.append(
                {
                    "name": name,
                    "credits_used": spent,
                    "daily_budget": daily_budget,
                    "period_budget": period_budget,
                    "pct_of_budget": pct_used,
                    "over_budget": (spent > period_budget if period_budget is not None else False),
                }
            )
        records.sort(key=lambda x: x["credits_used"], reverse=True)
        return records

    return {
        "users": _make_records(user_credits, user_budgets),
        "roles": _make_records(role_credits, role_budgets),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of *data* (0–100)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_data) - 1)
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def _round_up_quota(credits: float) -> int:
    """Round a credit quota up to a clean milestone (10, 25, 50, 100, 250, …)."""
    milestones = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    for m in milestones:
        if credits <= m:
            return m
    # Above 10 000 — round up to nearest 5 000
    return int(math.ceil(credits / 5000) * 5000)
