import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  PiggyBank,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Download,
  ExternalLink,
} from 'lucide-react';
import { formatDistanceToNow, parseISO } from 'date-fns';
import clsx from 'clsx';
import { getAdvisor, runAdvisor } from '../api/client';
import type { AdvisorFinding } from '../api/client';

const SEVERITY_STYLES: Record<string, string> = {
  high: 'bg-red-500/15 text-red-300 border-red-500/40',
  medium: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  low: 'bg-blue-500/15 text-blue-300 border-blue-500/40',
  info: 'bg-gray-500/15 text-gray-300 border-gray-500/40',
};

const CATEGORY_LABELS: Record<string, string> = {
  compute: 'Compute',
  storage: 'Storage',
  cloud_services: 'Cloud services',
  governance: 'Guardrails',
  performance: 'Performance',
};

function money(v: number | undefined): string {
  const n = v ?? 0;
  return n >= 100
    ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : `$${n.toFixed(2)}`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="absolute top-2 right-2 flex items-center gap-1 text-xs px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600"
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? 'Copied' : 'Copy SQL'}
    </button>
  );
}

function FindingCard({ f, index }: { f: AdvisorFinding; index: number }) {
  const [open, setOpen] = useState(index < 3);
  return (
    <div className="border border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-4 px-5 py-4 bg-gray-800 hover:bg-gray-700/60 text-left"
      >
        <span
          className={clsx(
            'flex-shrink-0 text-xs font-semibold uppercase px-2 py-0.5 rounded border',
            SEVERITY_STYLES[f.severity],
          )}
        >
          {f.severity}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-100 text-sm">{f.title}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-400">
              {CATEGORY_LABELS[f.category] ?? f.category}
            </span>
          </div>
          <p className="text-xs text-gray-400 font-mono mt-1 break-all">{f.object_name}</p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {f.monthly_savings_usd > 0 ? (
            <span className="text-sm font-bold text-emerald-400 tabular-nums">
              {money(f.monthly_savings_usd)}/mo
            </span>
          ) : (
            <span className="text-xs text-gray-500">risk / perf</span>
          )}
          {open ? (
            <ChevronUp size={15} className="text-gray-500" />
          ) : (
            <ChevronDown size={15} className="text-gray-500" />
          )}
        </div>
      </button>
      {open && (
        <div className="px-5 py-4 bg-gray-900 border-t border-gray-700 space-y-3 text-sm">
          <p className="text-gray-300">
            <span className="font-semibold text-gray-200">Why: </span>
            {f.evidence}
          </p>
          <p className="text-gray-300">
            <span className="font-semibold text-gray-200">Fix: </span>
            {f.recommendation}{' '}
            {f.docs_url && (
              <a
                href={f.docs_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-frost-400 hover:underline"
              >
                Snowflake docs <ExternalLink size={11} />
              </a>
            )}
          </p>
          {f.fix_sql && (
            <div className="relative">
              <pre className="bg-gray-950 text-sky-100 text-xs rounded-lg p-4 pr-24 overflow-x-auto">
                {f.fix_sql}
              </pre>
              <CopyButton text={f.fix_sql} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Savings() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ['advisor'], queryFn: getAdvisor });
  const run = useMutation({
    mutationFn: () => runAdvisor(30),
    onSuccess: (res) => qc.setQueryData(['advisor'], res),
  });
  const [category, setCategory] = useState('all');

  const findings = useMemo(
    () =>
      (data?.findings ?? []).filter((f) => category === 'all' || f.category === category),
    [data, category],
  );
  const categories = useMemo(
    () => Array.from(new Set((data?.findings ?? []).map((f) => f.category))),
    [data],
  );
  const pct =
    data?.monthly_compute_spend_usd && data.monthly_compute_spend_usd > 0
      ? Math.round((100 * data.monthly_savings_usd) / data.monthly_compute_spend_usd)
      : null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <PiggyBank className="text-emerald-400" size={24} /> Savings Advisor
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Rule-based checks across warehouses, storage, and cloud services, each with a dollar
            estimate and the SQL to fix it. Read-only: FrostWatch never runs the fixes for you.
          </p>
        </div>
        <div className="flex gap-2">
          {data?.generated_at && (
            <a
              href="/api/advisor/report.html"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-600 text-sm text-gray-200 hover:bg-gray-800"
            >
              <Download size={14} /> Shareable report
            </a>
          )}
          <button
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-frost-600 hover:bg-frost-500 text-sm text-white disabled:opacity-60"
          >
            <RefreshCw size={14} className={clsx(run.isPending && 'animate-spin')} />
            {run.isPending ? 'Auditing…' : 'Run audit now'}
          </button>
        </div>
      </div>

      {run.error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {(run.error as Error).message}
        </div>
      )}
      {error && <div className="text-sm text-red-300">{(error as Error).message}</div>}

      {isLoading ? (
        <div className="text-gray-400 text-sm">Loading…</div>
      ) : !data?.generated_at ? (
        <div className="border border-dashed border-gray-700 rounded-xl p-10 text-center">
          <PiggyBank className="mx-auto text-gray-500" size={36} />
          <p className="text-gray-200 font-semibold mt-3">No audit yet</p>
          <p className="text-sm text-gray-400 mt-1">
            An audit runs after every sync. Click <b>Run audit now</b> to start one, or run{' '}
            <code className="bg-gray-800 px-1.5 py-0.5 rounded">frostwatch audit</code> from your
            terminal.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
              <p className="text-xs uppercase tracking-wide text-gray-400">Estimated savings</p>
              <p className="text-3xl font-bold text-emerald-400 mt-1">
                {money(data.monthly_savings_usd)}
                <span className="text-base text-gray-400">/mo</span>
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {money(data.annual_savings_usd ?? data.monthly_savings_usd * 12)} per year
              </p>
            </div>
            <div className="rounded-xl border border-gray-700 bg-gray-800 p-5">
              <p className="text-xs uppercase tracking-wide text-gray-400">Warehouse compute</p>
              <p className="text-3xl font-bold text-gray-100 mt-1">
                {money(data.monthly_compute_spend_usd)}
                <span className="text-base text-gray-400">/mo</span>
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {pct !== null ? `savings are ${pct}% of compute` : ' '}
              </p>
            </div>
            <div className="rounded-xl border border-gray-700 bg-gray-800 p-5">
              <p className="text-xs uppercase tracking-wide text-gray-400">Findings</p>
              <p className="text-3xl font-bold text-gray-100 mt-1">{data.findings.length}</p>
              <p className="text-xs text-gray-400 mt-1">
                {data.demo ? 'demo data · ' : ''}updated{' '}
                {formatDistanceToNow(parseISO(data.generated_at), { addSuffix: true })}
              </p>
            </div>
          </div>

          {categories.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              {['all', ...categories].map((c) => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  className={clsx(
                    'text-xs px-3 py-1.5 rounded-full border',
                    category === c
                      ? 'bg-frost-600 border-frost-500 text-white'
                      : 'border-gray-700 text-gray-300 hover:bg-gray-800',
                  )}
                >
                  {c === 'all' ? 'All' : (CATEGORY_LABELS[c] ?? c)}
                </button>
              ))}
            </div>
          )}

          <div className="space-y-3">
            {findings.map((f, i) => (
              <FindingCard key={`${f.check_id}-${f.object_name}`} f={f} index={i} />
            ))}
          </div>

          {data.skipped && Object.keys(data.skipped).length > 0 && (
            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4 text-sm">
              <p className="font-semibold text-gray-200 mb-2">Checks that could not run</p>
              <ul className="space-y-1 text-gray-400">
                {Object.entries(data.skipped).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-mono text-gray-300">{k}</span>: {v}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-gray-500 mt-2">
                Usually fixed with{' '}
                <code>GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE &lt;role&gt;;</code>
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
