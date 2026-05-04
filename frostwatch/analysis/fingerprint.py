"""SQL query fingerprinting — normalize SQL to a canonical form and group similar queries."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import UTC, datetime


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def normalize_sql(sql: str) -> str:
    """Collapse a SQL string to its canonical fingerprint form.

    Transformations applied (in order):
    1. Strip ``--`` single-line comments
    2. Strip ``/* */`` block comments
    3. Replace string literals with ``'?'``
    4. Collapse ``IN (…)`` value lists to ``IN (?)``
    5. Replace numeric literals with ``?``
    6. Collapse whitespace
    7. Uppercase
    """
    if not sql:
        return ""

    # Strip single-line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    # Strip block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Replace string literals
    sql = re.sub(r"'(?:[^'\\]|\\.)*'", "'?'", sql)
    # Collapse IN lists (avoids treating large IN sets as distinct patterns)
    sql = re.sub(r"\bIN\s*\([^)]+\)", "IN (?)", sql, flags=re.IGNORECASE)
    # Replace numeric literals (integers and decimals, not inside identifiers)
    sql = re.sub(r"(?<![.\w])\d+(?:\.\d+)?(?![.\w])", "?", sql)
    # Collapse whitespace
    sql = re.sub(r"\s+", " ", sql).strip().upper()
    return sql


def fingerprint_sql(sql: str) -> str:
    """Return the MD5 hex digest of the normalized SQL."""
    return hashlib.md5(normalize_sql(sql).encode("utf-8")).hexdigest()


def build_fingerprints(queries: list[dict]) -> list[dict]:
    """Group CachedQuery dicts by SQL fingerprint.

    Expected keys in each dict: ``query_id``, ``query_text``, ``credits_used``,
    ``execution_time_ms``, ``start_time``, ``warehouse_name``, ``user_name``.

    Returns a list of fingerprint summary dicts, sorted by ``total_credits`` desc.
    """
    groups: dict[str, dict] = {}

    for q in queries:
        sql = q.get("query_text") or ""
        if not sql.strip():
            continue

        fp = fingerprint_sql(sql)
        credits = float(q.get("credits_used") or 0)
        exec_ms = float(q.get("execution_time_ms") or 0)
        start = _to_utc(q.get("start_time"))
        qid = str(q.get("query_id") or "")
        wh = str(q.get("warehouse_name") or "")
        user = str(q.get("user_name") or "")

        if fp not in groups:
            groups[fp] = {
                "fingerprint": fp,
                "canonical_sql": normalize_sql(sql)[:2000],
                "example_query_id": qid,
                "total_executions": 0,
                "total_credits": 0.0,
                "total_exec_ms": 0.0,
                "first_seen": start,
                "last_seen": start,
                "warehouses": defaultdict(int),
                "users": defaultdict(int),
            }

        g = groups[fp]
        g["total_executions"] += 1
        g["total_credits"] += credits
        g["total_exec_ms"] += exec_ms

        if start is not None:
            first = _to_utc(g["first_seen"])
            last = _to_utc(g["last_seen"])
            if first is None or start < first:
                g["first_seen"] = start
            if last is None or start > last:
                g["last_seen"] = start
                g["example_query_id"] = qid  # most-recent execution as the example

        if wh:
            g["warehouses"][wh] += 1
        if user:
            g["users"][user] += 1

    result = []
    for g in groups.values():
        n = g["total_executions"]
        warehouses: dict[str, int] = g["warehouses"]
        users: dict[str, int] = g["users"]
        most_wh = max(warehouses, key=warehouses.__getitem__) if warehouses else None
        most_user = max(users, key=users.__getitem__) if users else None
        result.append(
            {
                "fingerprint": g["fingerprint"],
                "canonical_sql": g["canonical_sql"],
                "example_query_id": g["example_query_id"],
                "total_executions": n,
                "total_credits": round(g["total_credits"], 6),
                "avg_credits": round(g["total_credits"] / n, 6) if n else 0.0,
                "avg_execution_ms": round(g["total_exec_ms"] / n, 1) if n else 0.0,
                "first_seen": g["first_seen"],
                "last_seen": g["last_seen"],
                "most_common_warehouse": most_wh,
                "most_common_user": most_user,
            }
        )

    result.sort(key=lambda x: x["total_credits"], reverse=True)
    return result


def detect_regressions(
    queries: list[dict],
    threshold: float = 2.0,
    top_n: int = 10,
) -> list[dict]:
    """Find query patterns that became more expensive this week vs the previous week.

    Args:
        queries: All cached query dicts (expects ``start_time``, ``query_text``,
                 ``credits_used``, ``warehouse_name``).
        threshold: Minimum avg-credits ratio (this week / last week) to flag.
        top_n:    Return at most this many regressions.

    Returns:
        List of regression dicts sorted by impact (ratio × executions), descending.
    """
    now = datetime.now(UTC)
    week_ago = now.replace(microsecond=0) - _td(days=7)
    two_weeks_ago = now.replace(microsecond=0) - _td(days=14)

    this_week: dict[str, list[float]] = defaultdict(list)
    last_week: dict[str, list[float]] = defaultdict(list)
    fp_meta: dict[str, dict] = {}

    for q in queries:
        sql = q.get("query_text") or ""
        if not sql.strip():
            continue
        start = _to_utc(q.get("start_time"))
        if start is None:
            continue

        fp = fingerprint_sql(sql)
        credits = float(q.get("credits_used") or 0)
        wh = str(q.get("warehouse_name") or "")

        if fp not in fp_meta:
            fp_meta[fp] = {
                "canonical_sql": normalize_sql(sql)[:200],
                "example_query_id": str(q.get("query_id") or ""),
                "warehouses": defaultdict(int),
            }
        if wh:
            fp_meta[fp]["warehouses"][wh] += 1

        if start >= week_ago:
            this_week[fp].append(credits)
        elif start >= two_weeks_ago:
            last_week[fp].append(credits)

    regressions = []
    for fp, this_list in this_week.items():
        if fp not in last_week:
            continue
        last_list = last_week[fp]
        avg_this = sum(this_list) / len(this_list)
        avg_last = sum(last_list) / len(last_list)
        if avg_last < 1e-9:
            continue
        ratio = avg_this / avg_last
        if ratio < threshold:
            continue

        meta = fp_meta[fp]
        warehouses: dict[str, int] = meta["warehouses"]
        most_wh = max(warehouses, key=warehouses.__getitem__) if warehouses else None
        regressions.append(
            {
                "fingerprint": fp,
                "canonical_sql_preview": meta["canonical_sql"],
                "example_query_id": meta["example_query_id"],
                "avg_credits_this_week": round(avg_this, 6),
                "avg_credits_last_week": round(avg_last, 6),
                "regression_ratio": round(ratio, 2),
                "executions_this_week": len(this_list),
                "executions_last_week": len(last_list),
                "most_common_warehouse": most_wh,
                "severity": ("critical" if ratio >= 5.0 else "high" if ratio >= 3.0 else "medium"),
            }
        )

    regressions.sort(
        key=lambda x: x["regression_ratio"] * x["executions_this_week"],
        reverse=True,
    )
    return regressions[:top_n]


def _td(**kwargs):  # noqa: ANN202 — tiny helper to avoid importing timedelta at top level
    from datetime import timedelta

    return timedelta(**kwargs)
