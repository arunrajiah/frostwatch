import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  DollarSign, Zap, Search, AlertTriangle, RefreshCw,
  ChevronDown, ChevronUp, FileText, Wind,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import clsx from 'clsx';
import { getDashboard, generateReport } from '../api/client';
import MetricCard from '../components/MetricCard';
import AnomalyBadge from '../components/AnomalyBadge';
import type { AnomalyResponse } from '../api/client';

const COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fb923c', '#f472b6', '#a78bfa'];

function formatUSD(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n);
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={clsx('bg-gray-700 rounded animate-pulse', className)} />;
}

function AnomalyRow({ anomaly }: { anomaly: AnomalyResponse }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-start gap-3 px-4 py-3 bg-gray-800 hover:bg-gray-750 text-left transition-colors duration-150"
        onClick={() => setExpanded((v) => !v)}
      >
        <AnomalyBadge severity={anomaly.severity} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-200">{anomaly.warehouse_name}</span>
            <span className="text-xs text-gray-500">{anomaly.anomaly_type}</span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 truncate">{anomaly.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-gray-500">
            {(() => { try { return format(parseISO(anomaly.detected_at), 'MMM d, HH:mm'); } catch { return anomaly.detected_at; } })()}
          </span>
          {expanded ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
        </div>
      </button>
      {expanded && anomaly.llm_explanation && (
        <div className="px-4 py-3 bg-gray-900 border-t border-gray-700">
          <p className="text-xs font-semibold text-frost-400 mb-1.5 flex items-center gap-1">
            <Wind size={12} /> AI Explanation
          </p>
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {anomaly.llm_explanation}
          </p>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [reportResult, setReportResult] = useState<{ id: number; summary_text: string } | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  });

  const reportMutation = useMutation({
    mutationFn: generateReport,
    onSuccess: (r) => {
      setReportResult({ id: r.id, summary_text: r.summary_text });
      setReportError(null);
    },
    onError: (err: Error) => {
      setReportError(err.message);
    },
  });

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-400">
        <AlertTriangle size={40} className="text-red-400" />
        <p className="text-lg font-medium text-gray-200">Failed to load dashboard</p>
        <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 hover:bg-frost-500/20 transition-colors text-sm"
        >
          <RefreshCw size={15} /> Retry
        </button>
      </div>
    );
  }

  const warehouseChartData = (data?.top_warehouses ?? []).map((w) => ({
    name: w.name,
    cost: Number(w.cost_usd.toFixed(2)),
    credits: Number(w.credits.toFixed(2)),
  }));

  const userChartData = (data?.top_users ?? []).map((u) => ({
    name: u.name,
    cost: Number(u.cost_usd.toFixed(2)),
    credits: Number(u.credits.toFixed(2)),
  }));

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Snowflake cost &amp; query observability</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          title="7-Day Spend"
          value={isLoading ? '…' : formatUSD(data?.total_cost_7d ?? 0)}
          subtitle={`${(data?.total_credits_7d ?? 0).toFixed(2)} credits`}
          icon={<DollarSign size={18} />}
          loading={isLoading}
        />
        <MetricCard
          title="30-Day Spend"
          value={isLoading ? '…' : formatUSD(data?.total_cost_30d ?? 0)}
          subtitle={`${(data?.total_credits_30d ?? 0).toFixed(2)} credits`}
          icon={<Zap size={18} />}
          loading={isLoading}
        />
        <MetricCard
          title="7-Day Queries"
          value={isLoading ? '…' : (data?.query_count_7d ?? 0).toLocaleString()}
          subtitle="total executions"
          icon={<Search size={18} />}
          loading={isLoading}
        />
        <MetricCard
          title="Anomalies Detected"
          value={isLoading ? '…' : (data?.recent_anomalies?.length ?? 0)}
          subtitle="in recent period"
          icon={<AlertTriangle size={18} />}
          loading={isLoading}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Top Warehouses */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">
            Top Warehouses — 7d Cost
          </h3>
          {isLoading ? (
            <SkeletonBlock className="h-52" />
          ) : warehouseChartData.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-gray-500 text-sm">No data</div>
          ) : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={180}>
                <PieChart>
                  <Pie
                    data={warehouseChartData}
                    dataKey="cost"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    strokeWidth={0}
                  >
                    {warehouseChartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                    itemStyle={{ color: '#e5e7eb' }}
                    formatter={(v: number) => [formatUSD(v), 'Cost']}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {warehouseChartData.map((w, i) => (
                  <div key={w.name} className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="text-xs text-gray-400 truncate flex-1">{w.name}</span>
                    <span className="text-xs font-medium text-white tabular-nums">
                      {formatUSD(w.cost)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top Users */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">
            Top Users — 7d Credits
          </h3>
          {isLoading ? (
            <SkeletonBlock className="h-52" />
          ) : userChartData.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-gray-500 text-sm">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={userChartData} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => v.toFixed(1)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={90}
                />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  itemStyle={{ color: '#e5e7eb' }}
                  formatter={(v: number) => [v.toFixed(4), 'Credits']}
                  cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                />
                <Bar dataKey="credits" fill="#818cf8" radius={[0, 4, 4, 0]} maxBarSize={24} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Recent Anomalies */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
            <AlertTriangle size={15} className="text-orange-400" />
            Recent Anomalies
          </h3>
          <a href="/anomalies" className="text-xs text-frost-400 hover:text-frost-300 transition-colors">
            View all →
          </a>
        </div>
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <SkeletonBlock key={i} className="h-14" />)}
          </div>
        ) : (data?.recent_anomalies ?? []).length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            No anomalies detected — all systems normal
          </div>
        ) : (
          <div className="space-y-2">
            {(data?.recent_anomalies ?? []).slice(0, 5).map((a) => (
              <AnomalyRow key={a.id} anomaly={a} />
            ))}
          </div>
        )}
      </div>

      {/* Generate Report */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              <FileText size={15} className="text-frost-400" />
              AI Report
            </h3>
            {data?.last_synced && (
              <p className="text-xs text-gray-500 mt-1">
                Last synced:{' '}
                {(() => { try { return format(parseISO(data.last_synced), 'PPpp'); } catch { return data.last_synced; } })()}
              </p>
            )}
          </div>
          <button
            onClick={() => reportMutation.mutate()}
            disabled={reportMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500 text-white text-sm font-medium hover:bg-frost-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {reportMutation.isPending ? (
              <>
                <RefreshCw size={15} className="animate-spin" /> Generating…
              </>
            ) : (
              <>
                <FileText size={15} /> Generate Report
              </>
            )}
          </button>
        </div>

        {reportError && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {reportError}
          </div>
        )}
        {reportResult && (
          <div className="mt-4 p-4 rounded-lg bg-gray-900 border border-gray-700">
            <p className="text-xs font-semibold text-frost-400 mb-2">Report #{reportResult.id} generated</p>
            <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
              {reportResult.summary_text}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
