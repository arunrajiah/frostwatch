// ─── Type Definitions ────────────────────────────────────────────────────────

export interface CostBreakdownItem {
  name: string;
  credits: number;
  cost_usd: number;
  pct_of_total: number;
}

export interface AnomalyResponse {
  id: number;
  detected_at: string;
  anomaly_type: string;
  warehouse_name: string;
  severity: string;
  description: string;
  llm_explanation: string;
}

export interface DashboardSummary {
  total_credits_7d: number;
  total_cost_7d: number;
  total_credits_30d: number;
  total_cost_30d: number;
  top_warehouses: CostBreakdownItem[];
  top_users: CostBreakdownItem[];
  recent_anomalies: AnomalyResponse[];
  last_synced: string | null;
  query_count_7d: number;
}

export interface QueryRecord {
  query_id: string;
  warehouse_name: string;
  user_name: string;
  role_name: string;
  execution_time_ms: number;
  bytes_scanned: number;
  credits_used: number;
  start_time: string;
  end_time: string;
  query_text_preview: string;
  query_tag: string;
  status: string;
}

export interface WarehouseAgg {
  warehouse_name: string;
  total_credits: number;
  total_cost_usd: number;
  query_count: number;
  avg_execution_ms: number;
}

export interface WarehouseMetric {
  warehouse_name: string;
  date: string;
  credits_used: number;
  cost_usd: number;
}

export interface ReportResponse {
  id: number;
  generated_at: string;
  period_start: string;
  period_end: string;
  summary_text: string;
  details_json: unknown;
}

export interface SettingsResponse {
  llm_provider: string;
  llm_model: string;
  llm_api_key_set: boolean;
  snowflake_account: string;
  snowflake_user: string;
  snowflake_warehouse: string;
  snowflake_database: string;
  snowflake_role: string;
  slack_webhook_url: string;
  email_recipients: string[];
  credits_per_dollar: number;
  schedule_cron: string;
  alert_threshold_multiplier: number;
}

export interface SyncStatus {
  status: string;
  last_run_at: string | null;
  last_error: string | null;
  rows_synced: number;
}

export interface SchedulerJob {
  job_id: string;
  name: string;
  next_run_time: string | null;
  trigger_description: string;
}

// ─── HTTP Helper ──────────────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    let message = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) message = body.detail;
      else if (body?.message) message = body.message;
    } catch {
      // use default message
    }
    throw new Error(message);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ─── API Functions ────────────────────────────────────────────────────────────

export const getDashboard = (): Promise<DashboardSummary> =>
  request<DashboardSummary>('/dashboard');

export const getQueries = (params: { days?: number; limit?: number } = {}): Promise<QueryRecord[]> => {
  const qs = new URLSearchParams();
  if (params.days) qs.set('days', String(params.days));
  if (params.limit) qs.set('limit', String(params.limit));
  return request<QueryRecord[]>(`/queries?${qs}`);
};

export const getWarehouses = (params: { days?: number } = {}): Promise<WarehouseAgg[]> => {
  const qs = new URLSearchParams();
  if (params.days) qs.set('days', String(params.days));
  return request<WarehouseAgg[]>(`/warehouses?${qs}`);
};

export const getWarehouseTimeseries = (params: {
  days?: number;
  warehouse?: string;
}): Promise<WarehouseMetric[]> => {
  const qs = new URLSearchParams();
  if (params.days) qs.set('days', String(params.days));
  if (params.warehouse) qs.set('warehouse', params.warehouse);
  return request<WarehouseMetric[]>(`/warehouses/timeseries?${qs}`);
};

export const getAnomalies = (params: { days?: number } = {}): Promise<AnomalyResponse[]> => {
  const qs = new URLSearchParams();
  if (params.days) qs.set('days', String(params.days));
  return request<AnomalyResponse[]>(`/anomalies?${qs}`);
};

export const getReports = (): Promise<ReportResponse[]> =>
  request<ReportResponse[]>('/reports');

export const generateReport = (): Promise<ReportResponse> =>
  request<ReportResponse>('/reports/generate', { method: 'POST' });

export const getReport = (id: number): Promise<ReportResponse> =>
  request<ReportResponse>(`/reports/${id}`);

export const getSettings = (): Promise<SettingsResponse> =>
  request<SettingsResponse>('/settings');

export const updateSettings = (data: Partial<SettingsResponse>): Promise<SettingsResponse> =>
  request<SettingsResponse>('/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });

export const triggerSync = (): Promise<{ status: string }> =>
  request<{ status: string }>('/sync', { method: 'POST' });

export const getSyncStatus = (): Promise<SyncStatus> =>
  request<SyncStatus>('/sync/status');

export const getSchedulerJobs = (): Promise<SchedulerJob[]> =>
  request<SchedulerJob[]>('/scheduler/jobs');

export const triggerScheduler = (): Promise<{ status: string }> =>
  request<{ status: string }>('/scheduler/trigger', { method: 'POST' });
