from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel


class CostBreakdownItem(BaseModel):
    name: str
    credits: float
    cost_usd: float
    pct_of_total: float


class DailyUsage(BaseModel):
    date: str
    credits: float
    cost_usd: float


class CostBreakdown(BaseModel):
    total_credits: float
    total_cost_usd: float
    by_warehouse: list[CostBreakdownItem]
    by_user: list[CostBreakdownItem]
    by_query_tag: list[CostBreakdownItem]
    by_date: list[DailyUsage]


def _pct(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


def compute_cost_breakdown(
    queries: list[dict],
    warehouse_metrics: list[dict],
    credits_per_dollar: float,
) -> CostBreakdown:
    total_credits = sum(
        float(r.get("credits_used") or 0) for r in warehouse_metrics
    )
    total_cost_usd = total_credits / credits_per_dollar if credits_per_dollar else 0.0

    wh_credits: dict[str, float] = defaultdict(float)
    for r in warehouse_metrics:
        name = r.get("warehouse_name") or "UNKNOWN"
        wh_credits[name] += float(r.get("credits_used") or 0)

    by_warehouse = [
        CostBreakdownItem(
            name=name,
            credits=round(credits, 4),
            cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
            pct_of_total=_pct(credits, total_credits),
        )
        for name, credits in sorted(wh_credits.items(), key=lambda x: -x[1])
    ]

    user_credits: dict[str, float] = defaultdict(float)
    for q in queries:
        user = q.get("user_name") or "UNKNOWN"
        user_credits[user] += float(q.get("credits_used") or 0)

    user_total = sum(user_credits.values()) or 1.0
    by_user = [
        CostBreakdownItem(
            name=name,
            credits=round(credits, 4),
            cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
            pct_of_total=_pct(credits, user_total),
        )
        for name, credits in sorted(user_credits.items(), key=lambda x: -x[1])[:10]
    ]

    tag_credits: dict[str, float] = defaultdict(float)
    for q in queries:
        tag = q.get("query_tag") or "(none)"
        tag_credits[tag] += float(q.get("credits_used") or 0)

    tag_total = sum(tag_credits.values()) or 1.0
    by_query_tag = [
        CostBreakdownItem(
            name=name,
            credits=round(credits, 4),
            cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
            pct_of_total=_pct(credits, tag_total),
        )
        for name, credits in sorted(tag_credits.items(), key=lambda x: -x[1])[:10]
    ]

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    date_credits: dict[str, float] = defaultdict(float)
    for r in warehouse_metrics:
        raw_date = r.get("date")
        if raw_date is None:
            continue
        if isinstance(raw_date, datetime):
            d = raw_date.date()
        elif hasattr(raw_date, "isoformat"):
            d = raw_date
        else:
            continue
        date_str = d.isoformat()
        date_credits[date_str] += float(r.get("credits_used") or 0)

    by_date = sorted(
        [
            DailyUsage(
                date=date_str,
                credits=round(credits, 4),
                cost_usd=round(credits / credits_per_dollar if credits_per_dollar else 0, 4),
            )
            for date_str, credits in date_credits.items()
        ],
        key=lambda x: x.date,
    )

    return CostBreakdown(
        total_credits=round(total_credits, 4),
        total_cost_usd=round(total_cost_usd, 4),
        by_warehouse=by_warehouse,
        by_user=by_user,
        by_query_tag=by_query_tag,
        by_date=by_date,
    )
