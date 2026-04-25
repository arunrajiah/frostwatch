import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Search, AlertTriangle, RefreshCw, Zap, Database, Clock, User } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getQueries } from '../api/client';
import QueryTable from '../components/QueryTable';
import type { QueryRecord } from '../api/client';

function QueryModal({ query, onClose }: { query: QueryRecord; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-white">Query Detail</h2>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">{query.query_id}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Meta grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-5 border-b border-gray-800">
          {[
            { label: 'Warehouse', value: query.warehouse_name, icon: <Database size={13} /> },
            { label: 'User', value: query.user_name, icon: <User size={13} /> },
            { label: 'Role', value: query.role_name, icon: <User size={13} /> },
            { label: 'Status', value: query.status, icon: null },
            { label: 'Credits Used', value: query.credits_used.toFixed(6), icon: <Zap size={13} /> },
            {
              label: 'Exec Time',
              value: query.execution_time_ms < 1000
                ? `${query.execution_time_ms}ms`
                : `${(query.execution_time_ms / 1000).toFixed(2)}s`,
              icon: <Clock size={13} />,
            },
            {
              label: 'Bytes Scanned',
              value: `${(query.bytes_scanned / 1e9).toFixed(3)} GB`,
              icon: <Database size={13} />,
            },
            {
              label: 'Started',
              value: (() => { try { return format(parseISO(query.start_time), 'PPp'); } catch { return query.start_time; } })(),
              icon: <Clock size={13} />,
            },
            {
              label: 'Ended',
              value: (() => { try { return format(parseISO(query.end_time), 'PPp'); } catch { return query.end_time; } })(),
              icon: <Clock size={13} />,
            },
          ].map(({ label, value, icon }) => (
            <div key={label}>
              <p className="text-xs text-gray-500 flex items-center gap-1 mb-0.5">
                {icon} {label}
              </p>
              <p className="text-sm font-medium text-gray-200 break-all">{value}</p>
            </div>
          ))}
        </div>

        {/* Query text */}
        <div className="p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Query Text</p>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {query.query_text_preview}
          </pre>
          {query.query_tag && (
            <p className="mt-3 text-xs text-gray-500">
              Tag: <span className="text-gray-300">{query.query_tag}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Queries() {
  const [days, setDays] = useState(7);
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState('');
  const [selectedQuery, setSelectedQuery] = useState<QueryRecord | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['queries', days, limit],
    queryFn: () => getQueries({ days, limit }),
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase().trim();
    if (!q) return data;
    return data.filter(
      (r) =>
        r.query_text_preview?.toLowerCase().includes(q) ||
        r.user_name?.toLowerCase().includes(q) ||
        r.warehouse_name?.toLowerCase().includes(q) ||
        r.role_name?.toLowerCase().includes(q)
    );
  }, [data, search]);

  const totalCredits = filtered.reduce((sum, r) => sum + (r.credits_used ?? 0), 0);

  const btnCls = (active: boolean) =>
    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
      active
        ? 'bg-frost-500/20 text-frost-400 border border-frost-500/30'
        : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600 hover:text-gray-200'
    }`;

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Query Explorer</h1>
          <p className="text-sm text-gray-500 mt-0.5">Browse and analyze Snowflake query history</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search queries, users, warehouses…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-frost-500/50 focus:ring-1 focus:ring-frost-500/30 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Days filter */}
        <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
          {[7, 14, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={btnCls(days === d)}>
              {d}d
            </button>
          ))}
        </div>

        {/* Limit */}
        <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
          {[25, 50, 100].map((l) => (
            <button key={l} onClick={() => setLimit(l)} className={btnCls(limit === l)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {!isLoading && !isError && (
        <div className="flex items-center gap-4 text-sm text-gray-400">
          <span>
            <span className="text-white font-semibold">{filtered.length}</span> queries
            {search && ` matching "${search}"`}
          </span>
          <span className="text-gray-600">|</span>
          <span>
            <span className="text-frost-400 font-semibold">{totalCredits.toFixed(4)}</span> total credits
          </span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-gray-400">
          <AlertTriangle size={40} className="text-red-400" />
          <p className="text-lg font-medium text-gray-200">Failed to load queries</p>
          <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 hover:bg-frost-500/20 transition-colors text-sm"
          >
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="rounded-xl border border-gray-700 overflow-hidden animate-pulse">
          <div className="h-12 bg-gray-900" />
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-800 border-t border-gray-700" />
          ))}
        </div>
      )}

      {/* Table */}
      {!isLoading && !isError && (
        <QueryTable queries={filtered} onRowClick={(q) => setSelectedQuery(q)} />
      )}

      {/* Modal */}
      {selectedQuery && (
        <QueryModal query={selectedQuery} onClose={() => setSelectedQuery(null)} />
      )}
    </div>
  );
}
