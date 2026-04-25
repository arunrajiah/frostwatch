import { TrendingUp, TrendingDown } from 'lucide-react';
import clsx from 'clsx';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    direction: 'up' | 'down';
    label: string;
    positive?: boolean; // true if "up" is good (default: false — up spend is bad)
  };
  icon?: React.ReactNode;
  loading?: boolean;
}

export default function MetricCard({
  title,
  value,
  subtitle,
  trend,
  icon,
  loading = false,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 animate-pulse">
        <div className="flex items-center justify-between mb-4">
          <div className="h-3 w-24 bg-gray-700 rounded" />
          <div className="h-8 w-8 bg-gray-700 rounded-lg" />
        </div>
        <div className="h-8 w-32 bg-gray-700 rounded mb-2" />
        <div className="h-3 w-20 bg-gray-700 rounded" />
      </div>
    );
  }

  const isPositiveTrend =
    trend?.positive !== undefined
      ? trend.positive
        ? trend.direction === 'up'
        : trend.direction === 'down'
      : trend?.direction === 'down'; // default: down is good (lower spend)

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 hover:border-gray-600 transition-colors duration-150">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">{title}</p>
        {icon && (
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gray-900 text-frost-400">
            {icon}
          </div>
        )}
      </div>

      <p className="text-3xl font-bold text-white mb-1 tabular-nums">{value}</p>

      <div className="flex items-center gap-2 mt-2">
        {trend && (
          <span
            className={clsx(
              'flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded',
              isPositiveTrend
                ? 'text-green-400 bg-green-400/10'
                : 'text-red-400 bg-red-400/10'
            )}
          >
            {trend.direction === 'up' ? (
              <TrendingUp size={12} />
            ) : (
              <TrendingDown size={12} />
            )}
            {trend.label}
          </span>
        )}
        {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
      </div>
    </div>
  );
}
