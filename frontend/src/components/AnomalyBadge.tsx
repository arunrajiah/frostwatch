import { AlertOctagon, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import clsx from 'clsx';

interface AnomalyBadgeProps {
  severity: string;
  showLabel?: boolean;
}

export default function AnomalyBadge({ severity, showLabel = true }: AnomalyBadgeProps) {
  const s = severity.toLowerCase();

  const config = {
    critical: {
      cls: 'bg-red-500/15 text-red-400 border border-red-500/25',
      icon: AlertOctagon,
    },
    high: {
      cls: 'bg-orange-500/15 text-orange-400 border border-orange-500/25',
      icon: AlertTriangle,
    },
    medium: {
      cls: 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25',
      icon: AlertCircle,
    },
    low: {
      cls: 'bg-frost-500/15 text-frost-400 border border-frost-500/25',
      icon: Info,
    },
  };

  const { cls, icon: Icon } =
    config[s as keyof typeof config] ?? {
      cls: 'bg-gray-700 text-gray-400 border border-gray-600',
      icon: Info,
    };

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold',
        cls
      )}
    >
      <Icon size={11} />
      {showLabel && <span className="capitalize">{severity}</span>}
    </span>
  );
}
