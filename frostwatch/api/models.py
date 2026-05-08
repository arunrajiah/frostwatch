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


# ── v0.3 dbt Cloud models ─────────────────────────────────────────────────────


class DbtCloudRunRecord(BaseModel):
    id: int
    run_id: int
    job_id: int
    job_name: str | None = None
    environment_id: int | None = None
    environment_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    triggered_by: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    models_executed: int | None = None
    credits_used: float | None = None


class DbtJobCostRecord(BaseModel):
    job_id: int
    job_name: str | None = None
    environment_id: int | None = None
    environment_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    run_count: int
    total_credits: float
    total_cost_usd: float
    avg_duration_seconds: float | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None


class DbtEnvironmentCostRecord(BaseModel):
    environment_id: int | None = None
    environment_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    run_count: int
    total_credits: float
    total_cost_usd: float
    distinct_jobs: int


class DbtThresholdAlertRecord(BaseModel):
    id: int
    detected_at: datetime
    dbt_model: str
    period_start: datetime
    period_end: datetime
    credits_used: float
    threshold: float


class DbtModelMetadataRecord(BaseModel):
    model_name: str
    project_name: str | None = None
    owner: str | None = None
    description: str | None = None
    materialization: str | None = None
    tags: list[str] = []
    schema_name: str | None = None
    database_name: str | None = None


class DbtCloudSyncResponse(BaseModel):
    runs_synced: int
    jobs_enriched: int
    environments_enriched: int


# ── v0.4 Resource Monitor models ──────────────────────────────────────────────


class ResourceMonitorRecord(BaseModel):
    id: int
    name: str
    credit_quota: float | None = None
    used_credits: float | None = None
    remaining_credits: float | None = None
    level: str | None = None
    frequency: str | None = None
    notify_at_percentage: float | None = None
    suspend_at_percentage: float | None = None
    suspend_immediately_at_percentage: float | None = None
    warehouses: list[str] = []
    owner: str | None = None
    synced_at: datetime | None = None


class MonitorRecommendationRecord(BaseModel):
    warehouse_name: str
    avg_daily_credits: float
    p95_daily_credits: float
    monthly_credits_p95: float
    recommended_quota: int
    recommended_cost_usd: float
    frequency: str
    notify_at_percentage: float
    suspend_at_percentage: float
    suspend_immediately_at_percentage: float
    existing_monitor: str | None = None
    current_quota: float | None = None
    quota_status: str
    priority: str
    history_days_used: int


class ProximityAlertRecord(BaseModel):
    monitor_name: str | None = None
    warehouse_names: list[str] = []
    credit_quota: float
    used_credits: float
    remaining_credits: float
    used_pct: float
    nearest_trigger: str | None = None
    nearest_trigger_pct: float | None = None
    margin_to_trigger_ppt: float | None = None
    frequency: str | None = None
    severity: str


class BudgetUsageRecord(BaseModel):
    name: str
    credits_used: float
    daily_budget: float | None = None
    period_budget: float | None = None
    pct_of_budget: float | None = None
    over_budget: bool


class BudgetSummary(BaseModel):
    days: int
    users: list[BudgetUsageRecord]
    roles: list[BudgetUsageRecord]


class GenerateSqlResponse(BaseModel):
    warehouse_name: str
    monitor_name: str
    sql: str
