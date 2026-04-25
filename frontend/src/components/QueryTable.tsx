import { useState } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown, Clock, Database, User, Zap } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import clsx from 'clsx';
import type { QueryRecord } from '../api/client';

type SortKey = 'execution_time_ms' | 'bytes_scanned' | 'credits_used' | 'start_time';
type SortDir = 'asc' | 'desc';

interface QueryTableProps {
  queries: QueryRecord[];
  onRowClick: (query: QueryRecord) => void;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  const mb = bytes / 1e6;
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  return `${(bytes / 1e3).toFixed(0)} KB`;
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${(s / 60).toFixed(1)}m`;
}

function StatusPill({ status }: { status: string }) {
  const s = status.toLowerCase();
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        s === 'success' && 'bg-green-500/10 text-green-400',
        s === 'failed' && 'bg-red-500/10 text-red-400',
        s === 'running' && 'bg-frost-500/10 text-frost-400',
        !['success', 'failed', 'running'].includes(s) && 'bg-gray-700 text-gray-400'
      )}
    >
      {status}
    </span>
  );
}

function SortIcon({ col, sort }: { col: SortKey; sort: { key: SortKey; dir: SortDir } }) {
  if (sort.key !== col) return <ChevronsUpDown size={13} className="text-gray-600" />;
  return sort.dir === 'asc' ? (
    <ChevronUp size={13} className="text-frost-400" />
  ) : (
    <ChevronDown size={13} className="text-frost-400" />
  );
}

export default function QueryTable({ queries, onRowClick }: QueryTableProps) {
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({
    key: 'start_time',
    dir: 'desc',
  });

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }
    );
  };

  const sorted = [...queries].sort((a, b) => {
    const mul = sort.dir === 'asc' ? 1 : -1;
    if (sort.key === 'start_time') {
      return mul * (new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
    }
    return mul * ((a[sort.key] as number) - (b[sort.key] as number));
  });

  const thCls =
    'px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider cursor-pointer select-none hover:text-gray-200 transition-colors duration-150';

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-700">
      <table className="w-full text-sm">
        <thead className="bg-gray-900 border-b border-gray-700">
          <tr>
            <th className={thCls}>
              <span className="flex items-center gap-1">
                <Database size={13} /> Warehouse / User
              </span>
            </th>
            <th className={clsx(thCls, 'hidden md:table-cell')}>Status</th>
            <th
              className={clsx(thCls, 'hidden lg:table-cell')}
              onClick={() => toggleSort('execution_time_ms')}
            >
              <span className="flex items-center gap-1">
                <Clock size={13} /> Exec Time
                <SortIcon col="execution_time_ms" sort={sort} />
              </span>
            </th>
            <th
              className={clsx(thCls, 'hidden lg:table-cell')}
              onClick={() => toggleSort('bytes_scanned')}
            >
              <span className="flex items-center gap-1">
                <Database size={13} /> Scanned
                <SortIcon col="bytes_scanned" sort={sort} />
              </span>
            </th>
            <th className={thCls} onClick={() => toggleSort('credits_used')}>
              <span className="flex items-center gap-1">
                <Zap size={13} /> Credits
                <SortIcon col="credits_used" sort={sort} />
              </span>
            </th>
            <th className={thCls} onClick={() => toggleSort('start_time')}>
              <span className="flex items-center gap-1">
                <Clock size={13} /> Time
                <SortIcon col="start_time" sort={sort} />
              </span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {sorted.map((q) => (
            <tr
              key={q.query_id}
              onClick={() => onRowClick(q)}
              className="bg-gray-800 hover:bg-gray-750 cursor-pointer transition-colors duration-100 group"
              style={{ '--tw-bg-opacity': '1' } as React.CSSProperties}
            >
              <td className="px-4 py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium text-gray-200 group-hover:text-white transition-colors">
                    {q.warehouse_name}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <User size={11} />
                    {q.user_name}
                  </span>
                  <span
                    className="text-xs text-gray-500 truncate max-w-xs"
                    title={q.query_text_preview}
                  >
                    {q.query_text_preview?.slice(0, 80)}
                    {q.query_text_preview?.length > 80 ? '…' : ''}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                <StatusPill status={q.status} />
              </td>
              <td className="px-4 py-3 hidden lg:table-cell tabular-nums text-gray-300">
                {formatMs(q.execution_time_ms)}
              </td>
              <td className="px-4 py-3 hidden lg:table-cell tabular-nums text-gray-300">
                {formatBytes(q.bytes_scanned)}
              </td>
              <td className="px-4 py-3 tabular-nums">
                <span className="text-frost-400 font-medium">
                  {q.credits_used.toFixed(4)}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-400 text-xs tabular-nums whitespace-nowrap">
                {(() => {
                  try {
                    return format(parseISO(q.start_time), 'MMM d, HH:mm');
                  } catch {
                    return q.start_time;
                  }
                })()}
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-12 text-center text-gray-500 bg-gray-800">
                No queries found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
