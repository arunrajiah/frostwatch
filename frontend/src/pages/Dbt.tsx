import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Package, Zap, Clock, Hash } from 'lucide-react';
import { getDbtBreakdown } from '../api/client';
import type { DbtModelAgg } from '../api/client';

const COLORS = [
  '#38bdf8', '#818cf8', '#34d399', '#f472b6', '#fb923c',
  '#a78bfa', '#4ade80', '#f87171', '#facc15', '#22d3ee',
];

function fmt(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

interface TooltipPayload {
  payload?: DbtModelAgg;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload!;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs space-y-1 shadow-lg">
      <p className="font-semibold text-white">{d.dbt_model}</p>
      <p className="text-gray-400">Credits: <span className="text-frost-300">{d.total_credits.toFixed(4)}</span></p>
      <p className="text-gray-400">Cost: <span className="text-frost-300">${d.total_cost_usd.toFixed(4)}</span></p>
      <p className="text-gray-400">Queries: <span className="text-frost-300">{d.query_count}</span></p>
      <p className="text-gray-400">Avg time: <span className="text-frost-300">{fmt(d.avg_execution_ms)}</span></p>
    </div>
  );
}

export default function Dbt() {
  const [days, setDays] = useState(30);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dbt', days],
    queryFn: () => getDbtBreakdown({ days }),
  });

  const chartData = (data ?? []).slice(0, 15);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <Package size={20} className="text-frost-400" />
            dbt Model Costs
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Snowflake credits and query performance broken down by dbt model
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-frost-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {isError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
          Failed to load dbt breakdown.
        </div>
      )}

      {!isLoading && !isError && (!data || data.length === 0) && (
        <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
          <Package size={40} className="text-gray-600" />
          <p className="text-gray-400 font-medium">No dbt queries found</p>
          <p className="text-gray-500 text-sm max-w-sm">
            FrostWatch detects dbt models by parsing the <code className="bg-gray-800 px-1 rounded">query_tag</code> field
            set by dbt on every Snowflake query. Make sure your dbt profile has{' '}
            <code className="bg-gray-800 px-1 rounded">query_tag</code> enabled.
          </p>
        </div>
      )}

      {data && data.length > 0 && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <div className="flex items-center gap-2 text-gray-400 text-xs mb-2">
                <Package size={14} /> Models detected
              </div>
              <p className="text-2xl font-bold text-white">{data.length}</p>
            </div>
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <div className="flex items-center gap-2 text-gray-400 text-xs mb-2">
                <Zap size={14} /> Total credits
              </div>
              <p className="text-2xl font-bold text-frost-300">
                {data.reduce((s, r) => s + r.total_credits, 0).toFixed(4)}
              </p>
            </div>
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <div className="flex items-center gap-2 text-gray-400 text-xs mb-2">
                <Hash size={14} /> Total queries
              </div>
              <p className="text-2xl font-bold text-white">
                {data.reduce((s, r) => s + r.query_count, 0).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Bar chart — top 15 models by credits */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h2 className="text-sm font-medium text-gray-300 mb-4">
              Credits by model (top {chartData.length})
            </h2>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 16, right: 24 }}>
                <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="dbt_model"
                  width={160}
                  tick={{ fill: '#d1d5db', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="total_credits" radius={[0, 4, 4, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Detail table */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">Model</th>
                  <th className="px-4 py-3 text-right">Credits</th>
                  <th className="px-4 py-3 text-right">Cost (USD)</th>
                  <th className="px-4 py-3 text-right">Queries</th>
                  <th className="px-4 py-3 text-right">Avg time</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => (
                  <tr
                    key={row.dbt_model}
                    className="border-b border-gray-700/50 last:border-0 hover:bg-gray-700/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-frost-300 flex items-center gap-2">
                      <span
                        className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                        style={{ background: COLORS[i % COLORS.length] }}
                      />
                      {row.dbt_model}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-200">
                      <span className="flex items-center justify-end gap-1">
                        <Zap size={11} className="text-yellow-400" />
                        {row.total_credits.toFixed(6)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-200">
                      ${row.total_cost_usd.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400">{row.query_count}</td>
                    <td className="px-4 py-3 text-right text-gray-400 flex items-center justify-end gap-1">
                      <Clock size={11} />
                      {fmt(row.avg_execution_ms)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
