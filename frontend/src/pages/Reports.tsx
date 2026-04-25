import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, RefreshCw, AlertTriangle, Clock, ChevronRight, Wind } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getReports, generateReport } from '../api/client';
import type { ReportResponse } from '../api/client';

function fmtDate(str: string) {
  try { return format(parseISO(str), 'PPP'); }
  catch { return str; }
}

function fmtDateTime(str: string) {
  try { return format(parseISO(str), 'PPp'); }
  catch { return str; }
}

export default function Reports() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: reports, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: getReports,
  });

  const selected = reports?.find((r) => r.id === selectedId) ?? null;

  const genMutation = useMutation({
    mutationFn: generateReport,
    onSuccess: (r) => {
      setGenSuccess(`Report #${r.id} generated`);
      setGenError(null);
      setSelectedId(r.id);
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      setTimeout(() => setGenSuccess(null), 5000);
    },
    onError: (err: Error) => {
      setGenError(err.message);
      setGenSuccess(null);
    },
  });

  return (
    <div className="p-6 space-y-5 h-full">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Reports</h1>
          <p className="text-sm text-gray-500 mt-0.5">AI-generated cost and query analysis reports</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
          <button
            onClick={() => genMutation.mutate()}
            disabled={genMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500 text-white text-sm font-medium hover:bg-frost-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {genMutation.isPending ? (
              <><RefreshCw size={15} className="animate-spin" /> Generating…</>
            ) : (
              <><Wind size={15} /> Generate Report</>
            )}
          </button>
        </div>
      </div>

      {/* Feedback */}
      {genError && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {genError}
        </div>
      )}
      {genSuccess && (
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
          {genSuccess}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertTriangle size={40} className="text-red-400" />
          <p className="text-lg font-medium text-gray-200">Failed to load reports</p>
          <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 hover:bg-frost-500/20 transition-colors text-sm"
          >
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      )}

      {/* Two-panel layout */}
      {!isError && (
        <div className="flex gap-5 h-[calc(100vh-16rem)]">
          {/* Left: report list */}
          <div className="w-72 flex-shrink-0 flex flex-col gap-2 overflow-y-auto pr-1">
            {isLoading &&
              [...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="h-20 bg-gray-800 rounded-xl border border-gray-700 animate-pulse"
                />
              ))}

            {!isLoading && (reports ?? []).length === 0 && (
              <div className="text-center py-12 text-gray-500 text-sm">
                <FileText size={32} className="mx-auto mb-2 opacity-30" />
                No reports yet
              </div>
            )}

            {(reports ?? []).map((r) => (
              <button
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={`text-left p-4 rounded-xl border transition-all duration-150 ${
                  selectedId === r.id
                    ? 'bg-frost-500/10 border-frost-500/40 ring-1 ring-frost-500/20'
                    : 'bg-gray-800 border-gray-700 hover:border-gray-600'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FileText
                      size={15}
                      className={selectedId === r.id ? 'text-frost-400' : 'text-gray-500'}
                    />
                    <span className="text-xs font-semibold text-gray-300">Report #{r.id}</span>
                  </div>
                  {selectedId === r.id && (
                    <ChevronRight size={14} className="text-frost-400 flex-shrink-0" />
                  )}
                </div>
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-gray-400 flex items-center gap-1">
                    <Clock size={10} /> {fmtDateTime(r.generated_at)}
                  </p>
                  <p className="text-xs text-gray-500">
                    {fmtDate(r.period_start)} – {fmtDate(r.period_end)}
                  </p>
                </div>
                <p className="mt-2 text-xs text-gray-500 line-clamp-2">
                  {r.summary_text?.slice(0, 100)}…
                </p>
              </button>
            ))}
          </div>

          {/* Right: detail */}
          <div className="flex-1 overflow-y-auto">
            {!selected ? (
              <div className="h-full flex flex-col items-center justify-center gap-3 text-gray-500">
                <div className="w-16 h-16 rounded-2xl bg-gray-800 border border-gray-700 flex items-center justify-center">
                  <FileText size={28} className="text-gray-600" />
                </div>
                <p className="text-sm font-medium text-gray-400">Select a report to view</p>
                <p className="text-xs text-center max-w-xs">
                  Choose a report from the list or generate a new one
                </p>
              </div>
            ) : (
              <ReportDetail report={selected} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ReportDetail({ report }: { report: ReportResponse }) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-5">
      {/* Meta */}
      <div className="flex items-start justify-between flex-wrap gap-3 border-b border-gray-700 pb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FileText size={18} className="text-frost-400" />
            Report #{report.id}
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Generated {(() => { try { return format(parseISO(report.generated_at), 'PPp'); } catch { return report.generated_at; } })()}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">Period</p>
          <p className="text-sm text-gray-300 font-medium">
            {fmtDate(report.period_start)} – {fmtDate(report.period_end)}
          </p>
        </div>
      </div>

      {/* Summary */}
      <div>
        <p className="text-xs font-semibold text-frost-400 uppercase tracking-wider mb-3 flex items-center gap-1">
          <Wind size={12} /> AI Summary
        </p>
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap font-mono">
            {report.summary_text}
          </p>
        </div>
      </div>

      {/* Details */}
      {Boolean(report.details_json) && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Raw Details
          </p>
          <div className="bg-gray-950 rounded-lg border border-gray-800 p-4 overflow-x-auto">
            <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap">
              {typeof report.details_json === 'string'
                ? report.details_json
                : JSON.stringify(report.details_json as Record<string, unknown>, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
