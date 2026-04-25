import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  BarChart2,
  AlertTriangle,
  FileText,
  Settings,
  Wind,
  RefreshCw,
  Clock,
  ChevronRight,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { triggerSync, getSyncStatus } from '../api/client';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/queries', icon: Database, label: 'Queries' },
  { to: '/warehouses', icon: BarChart2, label: 'Warehouses' },
  { to: '/anomalies', icon: AlertTriangle, label: 'Anomalies' },
  { to: '/reports', icon: FileText, label: 'Reports' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: syncStatus } = useQuery({
    queryKey: ['syncStatus'],
    queryFn: getSyncStatus,
    refetchInterval: 30_000,
  });

  const syncMutation = useMutation({
    mutationFn: triggerSync,
    onSuccess: () => {
      setSyncMessage('Sync triggered successfully');
      setTimeout(() => setSyncMessage(null), 4000);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] });
    },
    onError: (err: Error) => {
      setSyncMessage(`Sync failed: ${err.message}`);
      setTimeout(() => setSyncMessage(null), 5000);
    },
  });

  const lastSynced = syncStatus?.last_run_at
    ? formatDistanceToNow(new Date(syncStatus.last_run_at), { addSuffix: true })
    : null;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      {/* Sidebar */}
      <aside className="flex flex-col w-64 min-h-screen bg-gray-950 border-r border-gray-800 flex-shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-800">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-frost-500/20 text-frost-400">
            <Wind size={20} />
          </div>
          <div>
            <span className="text-lg font-bold text-white tracking-tight">FrostWatch</span>
            <p className="text-xs text-gray-500 leading-none mt-0.5">Snowflake Observability</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 group',
                  isActive
                    ? 'bg-frost-500/15 text-frost-400'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={18}
                    className={clsx(
                      'flex-shrink-0 transition-colors duration-150',
                      isActive ? 'text-frost-400' : 'text-gray-500 group-hover:text-gray-300'
                    )}
                  />
                  <span>{label}</span>
                  {isActive && (
                    <ChevronRight size={14} className="ml-auto text-frost-400/60" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Sync Section */}
        <div className="px-3 py-4 border-t border-gray-800 space-y-3">
          {syncMessage && (
            <div
              className={clsx(
                'px-3 py-2 rounded-lg text-xs',
                syncMessage.startsWith('Sync failed')
                  ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                  : 'bg-green-500/10 text-green-400 border border-green-500/20'
              )}
            >
              {syncMessage}
            </div>
          )}

          {lastSynced && (
            <div className="flex items-center gap-2 px-3 text-xs text-gray-500">
              <Clock size={12} />
              <span>Synced {lastSynced}</span>
            </div>
          )}

          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-frost-500/10 text-frost-400 border border-frost-500/20 text-sm font-medium hover:bg-frost-500/20 transition-colors duration-150 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <RefreshCw
              size={15}
              className={clsx(syncMutation.isPending && 'animate-spin')}
            />
            {syncMutation.isPending ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-900">
        {children}
      </main>
    </div>
  );
}
