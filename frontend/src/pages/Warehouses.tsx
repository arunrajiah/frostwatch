import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, RefreshCw, Database, Zap, Clock, Search } from 'lucide-react';
import { getWarehouses, getWarehouseTimeseries } from '../api/client';
import CostChart from '../components/CostChart';

function formatUSD(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n);
}

function formatMs(ms: number) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Warehouses() {
  const [days, setDays] = useState(30);
  const [selectedWarehouse, setSelectedWarehouse] = useState<string | null>(null);

  const { data: warehouses, isLoading: warehousesLoading, isError, error, refetch } = useQuery({
    queryKey: ['warehouses', days],
    queryFn: () => getWarehouses({ days }),
  });

  const { data: timeseries, isLoading: timeseriesLoading } = useQuery({
    queryKey: ['warehouseTimeseries', days, selectedWarehouse],
    queryFn: () => getWarehouseTimeseries({ days, warehouse: selectedWarehouse ?? undefined }),
    enabled: !!selectedWarehouse,
  });

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
          <h1 className="text-2xl font-bold text-white">Warehouses</h1>
          <p className="text-sm text-gray-500 mt-0.5">Cost and performance by warehouse</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1 border border-gray-800">
            {[7, 14, 30].map((d) => (
              <button key={d} onClick={() => setDays(d)} className={btnCls(days === d)}>
                {d}d
              </button>
            ))}
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertTriangle size={40} className="text-red-400" />
          <p className="text-lg font-medium text-gray-200">Failed to load warehouses</p>
          <p className="text-sm text-gray-500">{(error as Error)?.message}</p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 hover:bg-frost-500/20 transition-colors text-sm"
          >
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      )}

      {/* Warehouse cards */}
      {warehousesLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-36 bg-gray-800 rounded-xl border border-gray-700 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {(warehouses ?? []).map((w) => (
            <button
              key={w.warehouse_name}
              onClick={() =>
                setSelectedWarehouse(
                  selectedWarehouse === w.warehouse_name ? null : w.warehouse_name
                )
              }
              className={`text-left p-5 rounded-xl border transition-all duration-150 ${
                selectedWarehouse === w.warehouse_name
                  ? 'bg-frost-500/10 border-frost-500/40 ring-1 ring-frost-500/30'
                  : 'bg-gray-800 border-gray-700 hover:border-gray-600'
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
                    <Database size={15} className="text-frost-400" />
                  </div>
                  <span className="font-semibold text-gray-200 text-sm">{w.warehouse_name}</span>
                </div>
                {selectedWarehouse === w.warehouse_name && (
                  <span className="text-xs text-frost-400 bg-frost-500/10 border border-frost-500/20 rounded-full px-2 py-0.5">
                    Selected
                  </span>
                )}
              </div>

              <p className="text-2xl font-bold text-white tabular-nums mb-1">
                {formatUSD(w.total_cost_usd)}
              </p>

              <div className="grid grid-cols-3 gap-2 mt-3">
                <div>
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Zap size={10} /> Credits
                  </p>
                  <p className="text-sm font-medium text-gray-300 tabular-nums">
                    {w.total_credits.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Search size={10} /> Queries
                  </p>
                  <p className="text-sm font-medium text-gray-300 tabular-nums">
                    {w.query_count.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <Clock size={10} /> Avg
                  </p>
                  <p className="text-sm font-medium text-gray-300 tabular-nums">
                    {formatMs(w.avg_execution_ms)}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Time series chart */}
      {selectedWarehouse && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-lg font-semibold text-white">{selectedWarehouse}</h2>
            <span className="text-sm text-gray-500">— {days}-day credit usage</span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <CostChart
              data={(timeseries ?? []).map((m) => ({ date: m.date, credits_used: m.credits_used }))}
              title="Daily Credits Used"
              dataKey="credits_used"
              color="#38bdf8"
              type="area"
              loading={timeseriesLoading}
              valueFormatter={(v) => v.toFixed(3)}
            />
            <CostChart
              data={(timeseries ?? []).map((m) => ({ date: m.date, cost_usd: m.cost_usd }))}
              title="Daily Cost (USD)"
              dataKey="cost_usd"
              color="#34d399"
              type="area"
              loading={timeseriesLoading}
              valueFormatter={(v) => `$${v.toFixed(2)}`}
            />
          </div>
        </div>
      )}

      {!warehousesLoading && !isError && (warehouses ?? []).length === 0 && (
        <div className="text-center py-16 text-gray-500">
          <Database size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No warehouse data found for this period</p>
        </div>
      )}
    </div>
  );
}
