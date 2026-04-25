import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Database, Zap, Bell, Clock, DollarSign, Save, RefreshCw,
  AlertTriangle, CheckCircle2, Eye, EyeOff, Play, ChevronDown, Wifi,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import {
  getSettings, updateSettings, getSchedulerJobs, triggerScheduler,
  testSnowflakeConnection, testEmailConnection,
} from '../api/client';
import type { SettingsResponse } from '../api/client';

const LLM_PROVIDERS = ['anthropic', 'openai', 'gemini', 'ollama'];

function describeCron(expr: string): string {
  if (!expr) return '';
  const parts = expr.trim().split(/\s+/);
  if (parts.length < 5) return expr;
  const [min, hour, dom, month, dow] = parts;
  if (min === '0' && dom === '*' && month === '*' && dow === '*')
    return `Every day at ${hour}:00`;
  if (min === '0' && dom === '*' && month === '*' && dow === '1')
    return `Every Monday at ${hour}:00`;
  if (min === '0' && dom === '*' && month === '*')
    return `Every day at ${hour}:00`;
  if (dom === '*' && month === '*' && dow === '*')
    return `Every hour at :${min}`;
  return 'Custom schedule';
}

interface SectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function Section({ title, icon, children }: SectionProps) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-700 flex items-center gap-2">
        <span className="text-frost-400">{icon}</span>
        <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">{title}</h2>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
}

function Field({ label, hint, children }: FieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1.5">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

const inputCls =
  'w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-frost-500/60 focus:ring-1 focus:ring-frost-500/30 transition-colors';

const selectCls =
  'w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-frost-500/60 focus:ring-1 focus:ring-frost-500/30 transition-colors';

interface PasswordFieldProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

function PasswordField({ value, onChange, placeholder }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${inputCls} pr-9`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
      >
        {visible ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Partial<SettingsResponse>>({});
  const [password, setPassword] = useState('');
  const [llmKey, setLlmKey] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [emailStr, setEmailStr] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [schedulerMsg, setSchedulerMsg] = useState<string | null>(null);
  const [snowflakeTestMsg, setSnowflakeTestMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [emailTestMsg, setEmailTestMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data: settings, isLoading, isError, error } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const { data: jobs, isLoading: jobsLoading, refetch: refetchJobs } = useQuery({
    queryKey: ['schedulerJobs'],
    queryFn: getSchedulerJobs,
  });

  useEffect(() => {
    if (settings) {
      setForm(settings);
      setEmailStr((settings.email_recipients ?? []).join(', '));
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<SettingsResponse>) => updateSettings(payload),
    onSuccess: () => {
      setSaveSuccess(true);
      setSaveError(null);
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setTimeout(() => setSaveSuccess(false), 4000);
    },
    onError: (err: Error) => {
      setSaveError(err.message);
      setSaveSuccess(false);
    },
  });

  const triggerMutation = useMutation({
    mutationFn: triggerScheduler,
    onSuccess: () => {
      setSchedulerMsg('Scheduler triggered successfully');
      refetchJobs();
      setTimeout(() => setSchedulerMsg(null), 4000);
    },
    onError: (err: Error) => {
      setSchedulerMsg(`Failed: ${err.message}`);
    },
  });

  const snowflakeTestMutation = useMutation({
    mutationFn: testSnowflakeConnection,
    onSuccess: (data) => {
      setSnowflakeTestMsg({ ok: true, text: data.message });
      setTimeout(() => setSnowflakeTestMsg(null), 5000);
    },
    onError: (err: Error) => {
      setSnowflakeTestMsg({ ok: false, text: err.message });
    },
  });

  const emailTestMutation = useMutation({
    mutationFn: testEmailConnection,
    onSuccess: (data) => {
      setEmailTestMsg({ ok: true, text: data.message });
      setTimeout(() => setEmailTestMsg(null), 5000);
    },
    onError: (err: Error) => {
      setEmailTestMsg({ ok: false, text: err.message });
    },
  });

  const set = (key: keyof SettingsResponse, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSave = () => {
    const payload: Partial<SettingsResponse> = {
      ...form,
      email_recipients: emailStr
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (password) (payload as Record<string, unknown>)['snowflake_password'] = password;
    if (llmKey) (payload as Record<string, unknown>)['llm_api_key'] = llmKey;
    if (smtpPassword) (payload as Record<string, unknown>)['email_smtp_password'] = smtpPassword;
    saveMutation.mutate(payload);
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-48 bg-gray-800 rounded-xl border border-gray-700 animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-400">
        <AlertTriangle size={40} className="text-red-400" />
        <p className="text-lg font-medium text-gray-200">Failed to load settings</p>
        <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
      </div>
    );
  }

  const cronDesc = describeCron(form.schedule_cron ?? '');

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-gray-500 mt-0.5">Configure FrostWatch connections and alerts</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500 text-white text-sm font-medium hover:bg-frost-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {saveMutation.isPending ? (
            <><RefreshCw size={15} className="animate-spin" /> Saving…</>
          ) : (
            <><Save size={15} /> Save Settings</>
          )}
        </button>
      </div>

      {/* Feedback */}
      {saveSuccess && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
          <CheckCircle2 size={15} /> Settings saved successfully
        </div>
      )}
      {saveError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertTriangle size={15} /> {saveError}
        </div>
      )}

      {/* Snowflake Connection */}
      <Section title="Snowflake Connection" icon={<Database size={16} />}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Account">
            <input
              type="text"
              value={form.snowflake_account ?? ''}
              onChange={(e) => set('snowflake_account', e.target.value)}
              placeholder="xy12345.us-east-1"
              className={inputCls}
            />
          </Field>
          <Field label="User">
            <input
              type="text"
              value={form.snowflake_user ?? ''}
              onChange={(e) => set('snowflake_user', e.target.value)}
              placeholder="FROSTWATCH_USER"
              className={inputCls}
            />
          </Field>
          <Field label="Password" hint="Leave blank to keep existing password">
            <PasswordField
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
            />
          </Field>
          <Field label="Warehouse">
            <input
              type="text"
              value={form.snowflake_warehouse ?? ''}
              onChange={(e) => set('snowflake_warehouse', e.target.value)}
              placeholder="COMPUTE_WH"
              className={inputCls}
            />
          </Field>
          <Field label="Database">
            <input
              type="text"
              value={form.snowflake_database ?? ''}
              onChange={(e) => set('snowflake_database', e.target.value)}
              placeholder="SNOWFLAKE"
              className={inputCls}
            />
          </Field>
          <Field label="Role">
            <input
              type="text"
              value={form.snowflake_role ?? ''}
              onChange={(e) => set('snowflake_role', e.target.value)}
              placeholder="ACCOUNTADMIN"
              className={inputCls}
            />
          </Field>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={() => snowflakeTestMutation.mutate()}
            disabled={snowflakeTestMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-700 text-gray-300 text-xs font-medium hover:bg-gray-600 transition-colors disabled:opacity-60"
          >
            {snowflakeTestMutation.isPending
              ? <><RefreshCw size={12} className="animate-spin" /> Testing…</>
              : <><Wifi size={12} /> Test Connection</>}
          </button>
          {snowflakeTestMsg && (
            <span className={`text-xs ${snowflakeTestMsg.ok ? 'text-green-400' : 'text-red-400'}`}>
              {snowflakeTestMsg.ok ? '✓' : '✗'} {snowflakeTestMsg.text}
            </span>
          )}
        </div>
      </Section>

      {/* LLM Configuration */}
      <Section title="LLM Configuration" icon={<Zap size={16} />}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Provider">
            <div className="relative">
              <select
                value={form.llm_provider ?? ''}
                onChange={(e) => set('llm_provider', e.target.value)}
                className={selectCls}
              >
                <option value="">Select provider</option>
                {LLM_PROVIDERS.map((p) => (
                  <option key={p} value={p} className="capitalize">
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>
          </Field>
          <Field label="Model">
            <input
              type="text"
              value={form.llm_model ?? ''}
              onChange={(e) => set('llm_model', e.target.value)}
              placeholder={
                form.llm_provider === 'anthropic'
                  ? 'claude-3-5-sonnet-20241022'
                  : form.llm_provider === 'openai'
                  ? 'gpt-4o'
                  : 'model-name'
              }
              className={inputCls}
            />
          </Field>
          <Field
            label="API Key"
            hint={
              settings?.llm_api_key_set
                ? 'An API key is already set — leave blank to keep it'
                : 'Enter your API key'
            }
          >
            <PasswordField
              value={llmKey}
              onChange={setLlmKey}
              placeholder={settings?.llm_api_key_set ? '(key set)' : 'sk-…'}
            />
          </Field>
          {form.llm_provider === 'ollama' && (
            <Field label="Base URL" hint="Ollama server URL">
              <input
                type="text"
                value={form.llm_base_url ?? ''}
                onChange={(e) => set('llm_base_url', e.target.value)}
                placeholder="http://localhost:11434"
                className={inputCls}
              />
            </Field>
          )}
        </div>
      </Section>

      {/* Alerts */}
      <Section title="Alerts" icon={<Bell size={16} />}>
        <div className="grid grid-cols-1 gap-4">
          <Field
            label="Slack Webhook URL"
            hint="Post anomaly alerts to a Slack channel"
          >
            <input
              type="url"
              value={form.slack_webhook_url ?? ''}
              onChange={(e) => set('slack_webhook_url', e.target.value)}
              placeholder="https://hooks.slack.com/services/…"
              className={inputCls}
            />
          </Field>
          <Field
            label="Email Recipients"
            hint="Comma-separated list of email addresses"
          >
            <input
              type="text"
              value={emailStr}
              onChange={(e) => setEmailStr(e.target.value)}
              placeholder="ops@example.com, data@example.com"
              className={inputCls}
            />
          </Field>

          {/* SMTP Configuration */}
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider pt-1">SMTP Configuration</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="SMTP Host">
              <input
                type="text"
                value={form.email_smtp_host ?? ''}
                onChange={(e) => set('email_smtp_host', e.target.value)}
                placeholder="smtp.example.com"
                className={inputCls}
              />
            </Field>
            <Field label="SMTP Port">
              <input
                type="number"
                value={form.email_smtp_port ?? 587}
                onChange={(e) => set('email_smtp_port', parseInt(e.target.value, 10))}
                className={`${inputCls} max-w-[120px]`}
              />
            </Field>
            <Field label="SMTP User">
              <input
                type="text"
                value={form.email_smtp_user ?? ''}
                onChange={(e) => set('email_smtp_user', e.target.value)}
                placeholder="user@example.com"
                className={inputCls}
              />
            </Field>
            <Field label="SMTP Password" hint="Leave blank to keep existing password">
              <PasswordField
                value={smtpPassword}
                onChange={setSmtpPassword}
                placeholder="••••••••"
              />
            </Field>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => emailTestMutation.mutate()}
              disabled={emailTestMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-700 text-gray-300 text-xs font-medium hover:bg-gray-600 transition-colors disabled:opacity-60"
            >
              {emailTestMutation.isPending
                ? <><RefreshCw size={12} className="animate-spin" /> Testing…</>
                : <><Wifi size={12} /> Test SMTP</>}
            </button>
            {emailTestMsg && (
              <span className={`text-xs ${emailTestMsg.ok ? 'text-green-400' : 'text-red-400'}`}>
                {emailTestMsg.ok ? '✓' : '✗'} {emailTestMsg.text}
              </span>
            )}
          </div>

          <Field
            label="Alert Threshold Multiplier"
            hint="Flag a cost spike if it exceeds X times the rolling average"
          >
            <input
              type="number"
              min={1}
              max={20}
              step={0.1}
              value={form.alert_threshold_multiplier ?? 3}
              onChange={(e) => set('alert_threshold_multiplier', parseFloat(e.target.value))}
              className={`${inputCls} max-w-[160px]`}
            />
          </Field>
        </div>
      </Section>

      {/* Scheduling */}
      <Section title="Scheduling" icon={<Clock size={16} />}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field
            label="Report Schedule (Cron)"
            hint={cronDesc ? `→ ${cronDesc}` : 'e.g. 0 8 * * 1 (every Monday at 8am)'}
          >
            <input
              type="text"
              value={form.schedule_cron ?? ''}
              onChange={(e) => set('schedule_cron', e.target.value)}
              placeholder="0 8 * * 1"
              className={inputCls}
            />
          </Field>
          <Field
            label="Sync Schedule (Cron)"
            hint={form.sync_cron ? `→ ${describeCron(form.sync_cron)}` : 'e.g. 0 */6 * * * (every 6 hours)'}
          >
            <input
              type="text"
              value={form.sync_cron ?? ''}
              onChange={(e) => set('sync_cron', e.target.value)}
              placeholder="0 */6 * * *"
              className={inputCls}
            />
          </Field>
        </div>

        {/* Scheduler jobs */}
        <div className="mt-2">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-300">Scheduled Jobs</p>
            <div className="flex items-center gap-2">
              {schedulerMsg && (
                <span className="text-xs text-frost-400">{schedulerMsg}</span>
              )}
              <button
                onClick={() => triggerMutation.mutate()}
                disabled={triggerMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-700 text-gray-300 text-xs font-medium hover:bg-gray-600 transition-colors disabled:opacity-60"
              >
                <Play size={12} /> Trigger Now
              </button>
              <button
                onClick={() => refetchJobs()}
                className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-700 transition-colors"
              >
                <RefreshCw size={13} />
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {jobsLoading && (
              <div className="h-12 bg-gray-700 rounded-lg animate-pulse" />
            )}
            {!jobsLoading && (jobs ?? []).length === 0 && (
              <p className="text-sm text-gray-500 py-2">No scheduled jobs configured</p>
            )}
            {(jobs ?? []).map((job) => (
              <div
                key={job.job_id}
                className="flex items-center justify-between px-4 py-3 bg-gray-900 rounded-lg border border-gray-700"
              >
                <div>
                  <p className="text-sm font-medium text-gray-200">{job.name}</p>
                  <p className="text-xs text-gray-500">{job.trigger_description}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-500">Next run</p>
                  <p className="text-xs font-medium text-gray-300 tabular-nums">
                    {job.next_run_time
                      ? (() => { try { return format(parseISO(job.next_run_time), 'MMM d, HH:mm'); } catch { return job.next_run_time; } })()
                      : '—'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Cost */}
      <Section title="Cost Configuration" icon={<DollarSign size={16} />}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field
            label="Credits per Dollar"
            hint="Used to calculate USD cost from Snowflake credits"
          >
            <input
              type="number"
              min={0.01}
              step={0.01}
              value={form.credits_per_dollar ?? 1}
              onChange={(e) => set('credits_per_dollar', parseFloat(e.target.value))}
              className={`${inputCls} max-w-[160px]`}
            />
          </Field>
          <Field
            label="Query Fetch Limit"
            hint="Max queries fetched per sync from Snowflake"
          >
            <input
              type="number"
              min={100}
              max={10000}
              step={100}
              value={form.snowflake_query_limit ?? 500}
              onChange={(e) => set('snowflake_query_limit', parseInt(e.target.value, 10))}
              className={`${inputCls} max-w-[160px]`}
            />
          </Field>
        </div>
      </Section>

      {/* Save button (bottom) */}
      <div className="flex justify-end pt-2 pb-6">
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-frost-500 text-white text-sm font-medium hover:bg-frost-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {saveMutation.isPending ? (
            <><RefreshCw size={15} className="animate-spin" /> Saving…</>
          ) : (
            <><Save size={15} /> Save Settings</>
          )}
        </button>
      </div>
    </div>
  );
}
