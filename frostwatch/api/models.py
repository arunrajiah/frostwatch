from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class QueryRecord(BaseModel):
    query_id: str
    warehouse_name: str | None = None
    user_name: str | None = None
    role_name: str | None = None
    execution_time_ms: float | None = None
    bytes_scanned: float | None = None
    credits_used: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    query_text_preview: str | None = None
    query_tag: str | None = None
    dbt_model: str | None = None
    status: str | None = None


class WarehouseMetric(BaseModel):
    warehouse_name: str
    date: str
    credits_used: float
    cost_usd: float


class WarehouseAgg(BaseModel):
    warehouse_name: str
    total_credits: float
    total_cost_usd: float
    query_count: int
    avg_execution_ms: float


class DbtModelAgg(BaseModel):
    dbt_model: str
    total_credits: float
    total_cost_usd: float
    query_count: int
    avg_execution_ms: float


class CostBreakdownItem(BaseModel):
    name: str
    credits: float
    cost_usd: float
    pct_of_total: float


class AnomalyResponse(BaseModel):
    id: int
    detected_at: datetime
    anomaly_type: str
    warehouse_name: str | None = None
    severity: str
    description: str | None = None
    llm_explanation: str | None = None


class DashboardSummary(BaseModel):
    total_credits_7d: float
    total_cost_7d: float
    total_credits_30d: float
    total_cost_30d: float
    top_warehouses: list[CostBreakdownItem]
    top_users: list[CostBreakdownItem]
    recent_anomalies: list[AnomalyResponse]
    last_synced: datetime | None = None
    query_count_7d: int


class ReportResponse(BaseModel):
    id: int
    generated_at: datetime
    period_start: datetime | None = None
    period_end: datetime | None = None
    summary_text: str | None = None
    details_json: Any | None = None


class SettingsResponse(BaseModel):
    llm_provider: str
    llm_model: str
    llm_base_url: str
    snowflake_account: str
    snowflake_user: str
    snowflake_warehouse: str
    snowflake_database: str
    snowflake_role: str
    slack_webhook_url_set: bool
    email_recipients: list[str]
    credits_per_dollar: float
    schedule_cron: str
    sync_cron: str
    snowflake_query_limit: int
    alert_threshold_multiplier: float
    llm_api_key_set: bool
    snowflake_password_set: bool
    email_smtp_host: str
    email_smtp_port: int
    email_smtp_user: str


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_role: str | None = None
    slack_webhook_url: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int | None = None
    email_smtp_user: str | None = None
    email_smtp_password: str | None = None
    email_recipients: list[str] | None = None
    credits_per_dollar: float | None = None
    schedule_cron: str | None = None
    sync_cron: str | None = None
    snowflake_query_limit: int | None = None
    alert_threshold_multiplier: float | None = None


class SyncStatus(BaseModel):
    status: str
    last_run_at: datetime | None = None
    last_error: str | None = None
    rows_synced: int | None = None


class SchedulerJob(BaseModel):
    job_id: str
    name: str
    next_run_time: str | None = None
    trigger_description: str


# ── v0.2 — Query deep-dive ────────────────────────────────────────────────────


class QueryFingerprintRecord(BaseModel):
    fingerprint: str
    canonical_sql: str
    example_query_id: str | None = None
    total_executions: int
    total_credits: float
    avg_credits: float
    avg_execution_ms: float
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    most_common_warehouse: str | None = None
    most_common_user: str | None = None


class QueryRegressionRecord(BaseModel):
    fingerprint: str
    canonical_sql_preview: str
    example_query_id: str | None = None
    avg_credits_this_week: float
    avg_credits_last_week: float
    regression_ratio: float
    executions_this_week: int
    executions_last_week: int
    most_common_warehouse: str | None = None
    severity: str


class CostForecastPoint(BaseModel):
    warehouse_name: str
    forecast_date: str
    predicted_credits: float
    predicted_cost_usd: float
    trend: str
    confidence: str
    projected_30d_credits: float
    projected_30d_cost_usd: float


class PartitionPruningRecord(BaseModel):
    fingerprint: str
    canonical_sql_preview: str
    example_query_id: str
    total_executions: int
    executions_analyzed: int
    avg_pruning_ratio: float
    avg_partitions_scanned: float
    avg_partitions_total: float
    avg_credits: float
    total_credits: float
    most_common_warehouse: str | None = None
    most_common_user: str | None = None
    severity: str
    recommendation: str


class QueryRewriteRequest(BaseModel):
    query_id: str


class QueryRewriteResponse(BaseModel):
    id: int
    query_id: str
    fingerprint: str | None = None
    rewrite_suggestion: str
    generated_at: datetime
