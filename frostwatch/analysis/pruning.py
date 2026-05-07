"""Partition pruning analysis — detect queries that scan too many micro-partitions.

Snowflake stores data in micro-partitions. When a query has good clustering key
alignment, Snowflake *prunes* (skips) micro-partitions that cannot contain matching
rows. A query that scans 95 % of partitions is performing a near-full-table-scan,
which is usually fixable with clustering keys or better WHERE filters.

``detect_poor_pruning`` groups queries by SQL fingerprint and surfaces patterns
where the average pruning ratio (partitions_scanned / partitions_total) is high,
weighted by credit cost so the most expensive offenders sort to the top.
"""

from __future__ import annotations

from collections import defaultdict

from frostwatch.analysis.fingerprint import fingerprint_sql, normalize_sql

# Pruning ratio thresholds — fraction of partitions scanned (0.0 = perfect, 1.0 = full scan)
_SEVERITY_CRITICAL = 0.9  # scanning ≥ 90 % of partitions
_SEVERITY_HIGH = 0.7  # scanning ≥ 70 %
_SEVERITY_MEDIUM = 0.5  # scanning ≥ 50 %

_RECOMMENDATIONS: dict[str, str] = {
    "critical": (
        "Add a clustering key on the high-cardinality filter column(s). "
        "This query scans nearly every micro-partition — even a basic cluster on the "
        "date/timestamp column typically achieves 80-95 % partition pruning."
    ),
    "high": (
        "Review WHERE clause filter columns and consider adding a clustering key. "
        "Pushing a high-selectivity filter (e.g. date range, status) earlier in the "
        "predicate reduces partitions scanned significantly."
    ),
    "medium": (
        "Partition pruning is below average. Confirm that filter columns are ordered "
        "by selectivity, and evaluate whether a clustering key on the most common "
        "filter column would reduce scan overhead."
    ),
}


def _severity(ratio: float) -> str:
    if ratio >= _SEVERITY_CRITICAL:
        return "critical"
    if ratio >= _SEVERITY_HIGH:
        return "high"
    return "medium"


def detect_poor_pruning(
    queries: list[dict],
    min_partitions: int = 100,
    min_ratio: float = 0.5,
    top_n: int = 20,
) -> list[dict]:
    """Find query patterns with poor partition pruning efficiency.

    Args:
        queries:        CachedQuery dicts — expected keys: ``query_id``,
                        ``query_text``, ``partitions_scanned``,
                        ``partitions_total``, ``credits_used``,
                        ``warehouse_name``, ``user_name``.
        min_partitions: Only consider executions where ``partitions_total``
                        is at least this value. Small tables have few
                        partitions and full scans are cheap there — filtering
                        them out avoids false-positive noise.
        min_ratio:      Minimum average pruning ratio (0.0–1.0) to include a
                        fingerprint in the results. Default 0.5 means only
                        patterns that scan at least 50 % of partitions on average.
        top_n:          Maximum number of results to return.

    Returns:
        List of pruning-issue dicts sorted by impact score
        (``avg_pruning_ratio × total_credits × executions_analyzed``) descending.
    """
    groups: dict[str, dict] = {}

    for q in queries:
        sql = q.get("query_text") or ""
        if not sql.strip():
            continue

        ps = q.get("partitions_scanned")
        pt = q.get("partitions_total")

        # Skip rows without partition data or below the noise floor
        if ps is None or pt is None:
            continue
        ps_f = float(ps)
        pt_f = float(pt)
        if pt_f < min_partitions:
            continue

        ratio = ps_f / pt_f if pt_f > 0 else 0.0

        fp = fingerprint_sql(sql)
        credits = float(q.get("credits_used") or 0)
        wh = str(q.get("warehouse_name") or "")
        user = str(q.get("user_name") or "")
        qid = str(q.get("query_id") or "")

        if fp not in groups:
            groups[fp] = {
                "fingerprint": fp,
                "canonical_sql_preview": normalize_sql(sql)[:300],
                "example_query_id": qid,
                "total_executions": 0,
                "executions_analyzed": 0,
                "sum_ratio": 0.0,
                "sum_partitions_scanned": 0.0,
                "sum_partitions_total": 0.0,
                "total_credits": 0.0,
                "warehouses": defaultdict(int),
                "users": defaultdict(int),
            }

        g = groups[fp]
        g["total_executions"] += 1
        g["executions_analyzed"] += 1
        g["sum_ratio"] += ratio
        g["sum_partitions_scanned"] += ps_f
        g["sum_partitions_total"] += pt_f
        g["total_credits"] += credits
        g["example_query_id"] = qid  # keep most-recently seen
        if wh:
            g["warehouses"][wh] += 1
        if user:
            g["users"][user] += 1

    # Also count total executions for fingerprints that had *some* partition data
    # by doing a second pass over all queries
    all_fp_counts: dict[str, int] = defaultdict(int)
    for q in queries:
        sql = q.get("query_text") or ""
        if sql.strip():
            all_fp_counts[fingerprint_sql(sql)] += 1
    for fp, g in groups.items():
        g["total_executions"] = all_fp_counts.get(fp, g["executions_analyzed"])

    result = []
    for g in groups.values():
        n = g["executions_analyzed"]
        if n == 0:
            continue
        avg_ratio = g["sum_ratio"] / n
        if avg_ratio < min_ratio:
            continue

        avg_ps = g["sum_partitions_scanned"] / n
        avg_pt = g["sum_partitions_total"] / n
        total_credits = g["total_credits"]
        sev = _severity(avg_ratio)

        warehouses: dict[str, int] = g["warehouses"]
        users: dict[str, int] = g["users"]
        most_wh = max(warehouses, key=warehouses.__getitem__) if warehouses else None
        most_user = max(users, key=users.__getitem__) if users else None

        result.append(
            {
                "fingerprint": g["fingerprint"],
                "canonical_sql_preview": g["canonical_sql_preview"],
                "example_query_id": g["example_query_id"],
                "total_executions": g["total_executions"],
                "executions_analyzed": n,
                "avg_pruning_ratio": round(avg_ratio, 4),
                "avg_partitions_scanned": round(avg_ps, 1),
                "avg_partitions_total": round(avg_pt, 1),
                "avg_credits": round(total_credits / n, 6),
                "total_credits": round(total_credits, 6),
                "most_common_warehouse": most_wh,
                "most_common_user": most_user,
                "severity": sev,
                "recommendation": _RECOMMENDATIONS[sev],
            }
        )

    # Sort by impact: ratio × total_credits × executions_analyzed
    result.sort(
        key=lambda x: x["avg_pruning_ratio"] * x["total_credits"] * x["executions_analyzed"],
        reverse=True,
    )
    return result[:top_n]
