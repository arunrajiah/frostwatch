import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface ChartDataPoint {
  date: string;
  [key: string]: string | number;
}

interface CostChartProps {
  data: ChartDataPoint[];
  title: string;
  dataKey: string;
  color?: string;
  type?: 'area' | 'bar';
  valueFormatter?: (v: number) => string;
  loading?: boolean;
}

const CustomTooltip = ({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
  formatter?: (v: number) => string;
}) => {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-sm font-semibold" style={{ color: p.color }}>
          {formatter ? formatter(p.value) : p.value.toFixed(4)}
        </p>
      ))}
    </div>
  );
};

export default function CostChart({
  data,
  title,
  dataKey,
  color = '#38bdf8',
  type = 'area',
  valueFormatter,
  loading = false,
}: CostChartProps) {
  const formattedData = data.map((d) => ({
    ...d,
    _label: (() => {
      try {
        return format(parseISO(d.date), 'MMM d');
      } catch {
        return d.date;
      }
    })(),
  }));

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 animate-pulse">
        <div className="h-4 w-32 bg-gray-700 rounded mb-4" />
        <div className="h-48 bg-gray-700 rounded" />
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
      <h3 className="text-sm font-semibold text-gray-300 mb-4 uppercase tracking-wider">{title}</h3>
      <ResponsiveContainer width="100%" height={200}>
        {type === 'area' ? (
          <AreaChart data={formattedData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id={`gradient-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="_label"
              tick={{ fill: '#6b7280', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => valueFormatter ? valueFormatter(v) : v.toFixed(2)}
            />
            <Tooltip
              content={<CustomTooltip formatter={valueFormatter} />}
              cursor={{ stroke: '#374151', strokeWidth: 1 }}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              fill={`url(#gradient-${dataKey})`}
              dot={false}
              activeDot={{ r: 4, fill: color, stroke: '#0a0c10', strokeWidth: 2 }}
            />
          </AreaChart>
        ) : (
          <BarChart data={formattedData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="_label"
              tick={{ fill: '#6b7280', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => valueFormatter ? valueFormatter(v) : String(v)}
            />
            <Tooltip
              content={<CustomTooltip formatter={valueFormatter} />}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, color: '#9ca3af' }}
            />
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={40} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
