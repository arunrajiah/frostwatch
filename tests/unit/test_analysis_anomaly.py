import pytest
from datetime import date, timedelta
from frostwatch.analysis.anomaly import detect_anomalies


def _make_metrics(warehouse: str, days: int, credits_per_day: float, spike_day: int | None = None, spike_multiplier: float = 5.0):
    today = date.today()
    metrics = []
    for i in range(days):
        d = today - timedelta(days=days - i)
        credits = credits_per_day * spike_multiplier if i == spike_day else credits_per_day
        metrics.append({"warehouse_name": warehouse, "date": str(d), "credits_used": credits})
    return metrics


class _Cfg:
    alert_threshold_multiplier = 3.0


def test_no_anomaly_stable():
    metrics = _make_metrics("WH", 30, 10.0)
    result = detect_anomalies(metrics, _Cfg())
    assert result == []


def test_spike_detected():
    metrics = _make_metrics("WH", 30, 10.0, spike_day=29, spike_multiplier=10.0)
    result = detect_anomalies(metrics, _Cfg())
    assert len(result) >= 1
    assert any(a.warehouse_name == "WH" for a in result)


def test_spike_factor_above_one():
    metrics = _make_metrics("WH", 30, 10.0, spike_day=29, spike_multiplier=10.0)
    result = detect_anomalies(metrics, _Cfg())
    anomaly = next(a for a in result if a.warehouse_name == "WH")
    assert anomaly.spike_factor > 1.0


def test_severity_critical_for_large_spike():
    metrics = _make_metrics("WH", 30, 10.0, spike_day=29, spike_multiplier=15.0)
    result = detect_anomalies(metrics, _Cfg())
    severities = {a.severity for a in result if a.warehouse_name == "WH"}
    assert severities & {"high", "critical"}


def test_empty_metrics():
    assert detect_anomalies([], _Cfg()) == []
