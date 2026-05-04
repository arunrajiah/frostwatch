"""Cost forecasting — project warehouse spend using linear regression on historical metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta


def _linreg(x: list[float], y: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) of the ordinary least-squares line through (x, y)."""
    n = len(x)
    if n < 2:
        return 0.0, (y[0] if y else 0.0)
    xm = sum(x) / n
    ym = sum(y) / n
    numer = sum((x[i] - xm) * (y[i] - ym) for i in range(n))
    denom = sum((x[i] - xm) ** 2 for i in range(n))
    slope = numer / denom if denom else 0.0
    return slope, ym - slope * xm


def forecast_warehouse_costs(
    metrics: list[dict],
    days_ahead: int = 7,
    history_days: int = 30,
    credits_per_dollar: float = 3.0,
) -> list[dict]:
    """Project daily warehouse credit usage for the next *days_ahead* days.

    Uses per-warehouse ordinary least-squares regression over the last
    *history_days* days of data.

    Args:
        metrics:          List of ``{warehouse_name, date, credits_used, cost_usd}``
                          dicts, e.g. from ``CachedWarehouseMetric``.
        days_ahead:       How many future days to project (default 7).
        history_days:     How many historical days to fit (default 30).
        credits_per_dollar: Conversion rate (default 3.0).

    Returns:
        List of forecast point dicts:
        ``{warehouse_name, forecast_date, predicted_credits, predicted_cost_usd,
           trend, confidence, projected_30d_credits, projected_30d_cost_usd}``
    """
    today = date.today()
    cutoff = today - timedelta(days=history_days)

    by_wh: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for m in metrics:
        d = m.get("date")
        if d is None:
            continue
        if hasattr(d, "date"):
            d = d.date()
        wh = m.get("warehouse_name") or ""
        credits = float(m.get("credits_used") or 0)
        if wh and isinstance(d, date) and d >= cutoff:
            by_wh[wh].append((d, credits))

    results: list[dict] = []
    for wh, pts in by_wh.items():
        pts.sort(key=lambda p: p[0])
        if len(pts) < 3:
            continue

        dates, ys_tuple = zip(*pts, strict=False)
        ys = list(ys_tuple)
        origin = dates[0]
        xs = [(d - origin).days for d in dates]

        slope, intercept = _linreg(xs, ys)

        last_x = xs[-1]
        avg_y = sum(ys) / len(ys)

        confidence: str
        if len(pts) >= 21:
            confidence = "high"
        elif len(pts) >= 7:
            confidence = "medium"
        else:
            confidence = "low"

        if abs(slope) < 0.005 * avg_y:
            trend = "stable"
        elif slope > 0:
            trend = "up"
        else:
            trend = "down"

        proj30 = sum(max(0.0, slope * (last_x + i + 1) + intercept) for i in range(30))
        proj30_cost = proj30 / credits_per_dollar if credits_per_dollar else 0.0

        for i in range(1, days_ahead + 1):
            pred = max(0.0, slope * (last_x + i) + intercept)
            fdate = dates[-1] + timedelta(days=i)
            results.append(
                {
                    "warehouse_name": wh,
                    "forecast_date": fdate.isoformat(),
                    "predicted_credits": round(pred, 4),
                    "predicted_cost_usd": round(pred / credits_per_dollar, 4)
                    if credits_per_dollar
                    else 0.0,
                    "trend": trend,
                    "confidence": confidence,
                    "projected_30d_credits": round(proj30, 2),
                    "projected_30d_cost_usd": round(proj30_cost, 2),
                }
            )

    results.sort(key=lambda r: (r["warehouse_name"], r["forecast_date"]))
    return results
