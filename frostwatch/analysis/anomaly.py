from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig


class AnomalyDetection(BaseModel):
    warehouse_name: str
    anomaly_type: str
    severity: str
    description: str
    spike_factor: float


def _severity_from_factor(factor: float) -> str:
    if factor >= 10.0:
        return "critical"
    if factor >= 5.0:
        return "high"
    if factor >= 3.0:
        return "medium"
    return "low"


def detect_anomalies(
    warehouse_metrics: list[dict],
    config: "FrostWatchConfig",
) -> list[AnomalyDetection]:
    today = datetime.now(timezone.utc).date()

    by_warehouse: dict[str, dict[date, float]] = defaultdict(dict)

    for row in warehouse_metrics:
        wh = row.get("warehouse_name") or "UNKNOWN"
        raw_date = row.get("date")
        credits = float(row.get("credits_used") or 0)

        if raw_date is None:
            continue
        if isinstance(raw_date, datetime):
            d = raw_date.date()
        elif isinstance(raw_date, date):
            d = raw_date
        else:
            try:
                d = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

        by_warehouse[wh][d] = by_warehouse[wh].get(d, 0.0) + credits

    anomalies: list[AnomalyDetection] = []

    for wh, date_credits in by_warehouse.items():
        window_7_start = today - timedelta(days=7)
        window_28_start = today - timedelta(days=28)

        recent_days = {d: c for d, c in date_credits.items() if d >= window_7_start}
        baseline_days = {
            d: c
            for d, c in date_credits.items()
            if window_28_start <= d < window_7_start
        }

        if not recent_days or not baseline_days:
            continue

        recent_avg = sum(recent_days.values()) / len(recent_days)
        baseline_avg = sum(baseline_days.values()) / len(baseline_days)

        if baseline_avg > 0:
            weekly_factor = recent_avg / baseline_avg
            if weekly_factor > config.alert_threshold_multiplier:
                severity = _severity_from_factor(weekly_factor)
                anomalies.append(
                    AnomalyDetection(
                        warehouse_name=wh,
                        anomaly_type="weekly_average_spike",
                        severity=severity,
                        description=(
                            f"Warehouse '{wh}' 7-day average credits ({recent_avg:.2f}/day) "
                            f"is {weekly_factor:.1f}x the prior 21-day baseline "
                            f"({baseline_avg:.2f}/day)."
                        ),
                        spike_factor=round(weekly_factor, 2),
                    )
                )

        all_days = list(date_credits.values())
        if len(all_days) < 7:
            continue

        overall_avg = sum(all_days) / len(all_days)
        if overall_avg <= 0:
            continue

        for d, credits in date_credits.items():
            daily_factor = credits / overall_avg
            if daily_factor > 3.0:
                severity = _severity_from_factor(daily_factor)
                anomalies.append(
                    AnomalyDetection(
                        warehouse_name=wh,
                        anomaly_type="daily_spike",
                        severity=severity,
                        description=(
                            f"Warehouse '{wh}' used {credits:.2f} credits on {d.isoformat()}, "
                            f"which is {daily_factor:.1f}x the 30-day average "
                            f"({overall_avg:.2f} credits/day)."
                        ),
                        spike_factor=round(daily_factor, 2),
                    )
                )

    anomalies.sort(key=lambda a: -a.spike_factor)
    return anomalies
