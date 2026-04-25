from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class QueryRecord(BaseModel):
    query_id: str
    warehouse_name: Optional[str] = None
    user_name: Optional[str] = None
    role_name: Optional[str] = None
    execution_time_ms: Optional[float] = None
    bytes_scanned: Optional[float] = None
    credits_used: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    query_text_preview: Optional[str] = None
    query_tag: Optional[str] = None
    status: Optional[str] = None


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


class CostBreakdownItem(BaseModel):
    name: str
    credits: float
    cost_usd: float
    pct_of_total: float


class AnomalyResponse(BaseModel):
    id: int
    detected_at: datetime
    anomaly_type: str
    warehouse_name: Optional[str] = None
    severity: str
    description: Optional[str] = None
    llm_explanation: Optional[str] = None


class DashboardSummary(BaseModel):
    total_credits_7d: float
    total_cost_7d: float
    total_credits_30d: float
    total_cost_30d: float
    top_warehouses: list[CostBreakdownItem]
    top_users: list[CostBreakdownItem]
    recent_anomalies: list[AnomalyResponse]
    last_synced: Optional[datetime] = None
    query_count_7d: int


class ReportResponse(BaseModel):
    id: int
    generated_at: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    summary_text: Optional[str] = None
    details_json: Optional[Any] = None


class SettingsResponse(BaseModel):
    llm_provider: str
    llm_model: str
    snowflake_account: str
    snowflake_user: str
    snowflake_warehouse: str
    snowflake_database: str
    snowflake_role: str
    slack_webhook_url: str
    email_recipients: list[str]
    credits_per_dollar: float
    schedule_cron: str
    alert_threshold_multiplier: float
    llm_api_key_set: bool
    snowflake_password_set: bool
    email_smtp_host: str
    email_smtp_port: int
    email_smtp_user: str


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    snowflake_account: Optional[str] = None
    snowflake_user: Optional[str] = None
    snowflake_password: Optional[str] = None
    snowflake_warehouse: Optional[str] = None
    snowflake_database: Optional[str] = None
    snowflake_role: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: Optional[int] = None
    email_smtp_user: Optional[str] = None
    email_smtp_password: Optional[str] = None
    email_recipients: Optional[list[str]] = None
    credits_per_dollar: Optional[float] = None
    schedule_cron: Optional[str] = None
    alert_threshold_multiplier: Optional[float] = None


class SyncStatus(BaseModel):
    status: str
    last_run_at: Optional[datetime] = None
    last_error: Optional[str] = None
    rows_synced: Optional[int] = None


class SchedulerJob(BaseModel):
    job_id: str
    name: str
    next_run_time: Optional[str] = None
    trigger_description: str
