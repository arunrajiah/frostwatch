import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, RefreshCw, ChevronDown, ChevronUp, Wind, Filter } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getAnomalies } from '../api/client';
import AnomalyBadge from '../components/AnomalyBadge';
import type { AnomalyResponse } from '../api/client';

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low'];

function AnomalyRow({ anomaly }: { anomaly: AnomalyResponse }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-4 px-5 py-4 bg-gray-800 hover:bg-gray-750 text-left transition-colors duration-150"
      >
        {/* Severity */}
        <div className="flex-shrink-0 pt-0.5">
          <AnomalyBadge severity={anomaly.severity} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-semibold text-gray-200 text-sm">{anomaly.warehouse_name}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-400">
              {anomaly.anomaly_type}
            </span>
          </div>
          <p className="text-sm text-gray-400">{anomaly.description}</p>
        </div>

        {/* Time + toggle */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-gray-500 tabular-nums">
            {(() => {
              try { return format(parseISO(anomaly.detected_at), 'MMM d, HH:mm'); }
              catch { return anomaly.detected_at; }
            })()}
          </span>
          {anomaly.llm_explanation
            ? expanded
              ? <ChevronUp size={15} className="text-gray-500" />
              : <ChevronDown size={15} className="text-gray-500" />
            : null}
        </div>
      </button>

      {expanded && anomaly.llm_explanation && (
        <div className="px-5 py-4 bg-gray-900 border-t border-gray-700">
          <p className="text-xs font-semibold text-frost-400 mb-2 flex items-center gap-1">
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

export default function Anomalies() {
  const [days, setDays] = useState(30);
  const [severity, setSeverity] = useState('all');
  const [warehouse, setWarehouse] = useState('all');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['anomalies', days],
    queryFn: () => getAnomalies({ days }),
  });

  const warehouses = useMemo(() => {
    const names = new Set((data ?? []).map((a) => a.warehouse_name));
    return ['all', ...Array.from(names).sort()];
  }, [data]);

  const filtered = useMemo(() => {
    let rows = data ?? [];
    if (severity !== 'all') rows = rows.filter((a) => a.severity.toLowerCase() === severity);
    if (warehouse !== 'all') rows = rows.filter((a) => a.warehouse_name === warehouse);
    // Sort: critical first, then by detected_at desc
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return [...rows].sort((a, b) => {
      const sd = (order[a.severity.toLowerCase()] ?? 9) - (order[b.severity.toLowerCase()] ?? 9);
      if (sd !== 0) return sd;
      return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
    });
  }, [data, severity, warehouse]);

  const btnCls = (active: boolean) =>
    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-150 capitalize ${
      active
        ? 'bg-frost-500/20 text-frost-400 border border-frost-500/30'
        : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600 hover:text-gray-200'
    }`;

  const selectCls =
    'bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-frost-500/50 transition-colors';

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Anomalies</h1>
          <p className="text-sm text-gray-500 mt-0.5">AI-detected cost and performance anomalies</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Filter size={12} /> Severity:
        </div>
        <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
          {SEVERITIES.map((s) => (
            <button key={s} onClick={() => setSeverity(s)} className={btnCls(severity === s)}>
              {s}
            </button>
          ))}
        </div>

        <select
          value={warehouse}
          onChange={(e) => setWarehouse(e.target.value)}
          className={selectCls}
        >
          {warehouses.map((w) => (
            <option key={w} value={w}>
              {w === 'all' ? 'All Warehouses' : w}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
          {[7, 14, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={btnCls(days === d)}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {!isLoading && !isError && (
        <p className="text-sm text-gray-400">
          <span className="text-white font-semibold">{filtered.length}</span> anomalies found
          {severity !== 'all' && ` · severity: ${severity}`}
          {warehouse !== 'all' && ` · warehouse: ${warehouse}`}
        </p>
      )}

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertTriangle size={40} className="text-red-400" />
          <p className="text-lg font-medium text-gray-200">Failed to load anomalies</p>
          <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 hover:bg-frost-500/20 transition-colors text-sm"
          >
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-xl border border-gray-700 animate-pulse" />
          ))}
        </div>
      )}

      {/* Anomaly list */}
      {!isLoading && !isError && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((a) => (
            <AnomalyRow key={a.id} anomaly={a} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-gray-500">
          <div className="w-16 h-16 rounded-2xl bg-gray-800 border border-gray-700 flex items-center justify-center">
            <AlertTriangle size={28} className="text-gray-600" />
          </div>
          <p className="text-base font-medium text-gray-400">No anomalies found</p>
          <p className="text-sm text-center max-w-xs">
            {severity !== 'all' || warehouse !== 'all'
              ? 'Try adjusting your filters'
              : 'No anomalies were detected in this period — all systems look normal'}
          </p>
        </div>
      )}
    </div>
  );
}
