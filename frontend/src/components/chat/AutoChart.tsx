"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from "recharts";
import { analyzeData, type DataPoint } from "./chartUtils";

const COLORS = [
  "#a78bfa", "#6ee7b7", "#fcd34d", "#fb923c", "#34d399",
  "#fbbf24", "#f87171", "#60a5fa", "#34d399", "#fbbf24",
];

function DataTable({ data }: { data: DataPoint[] }) {
  if (!data?.length) return null;
  const columns = Object.keys(data[0]);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-3 py-1.5 text-left border-b border-[var(--color-border)] text-[var(--color-text-muted)]">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 20).map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col} className="px-3 py-1 border-b border-[var(--color-border)]/50 text-[var(--color-text-muted)]">{String(row[col] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AutoChart({ data, title, suggestedType }: { data: unknown; title?: string; suggestedType?: string }) {
  const config = useMemo(() => analyzeData(data, suggestedType), [data, suggestedType]);

  if (!config) {
    return <p className="text-xs text-[var(--color-text-muted)]">Unable to visualize data</p>;
  }

  const chartTitle = title || config.title;
  const axisStyle = { fontSize: 11, fill: "#9ca3af" };
  const gridColor = "rgba(255,255,255,0.08)";
  const tooltipStyle = {
    backgroundColor: "#1e1e2e",
    border: "1px solid #333",
    borderRadius: "8px",
    color: "#e5e5e5",
    fontSize: "12px",
  };

  const renderChart = () => {
    switch (config.type) {
      case "bar":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={config.data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey={config.xKey} tick={axisStyle} />
              <YAxis tick={axisStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {config.yKeys?.map((key, i) => (
                <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
      case "line":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={config.data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey={config.xKey} tick={axisStyle} />
              <YAxis tick={axisStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {config.yKeys?.map((key, i) => (
                <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ fill: COLORS[i % COLORS.length], strokeWidth: 2, r: 3 }} activeDot={{ r: 6 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );
      case "pie":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={config.data} cx="50%" cy="50%" labelLine={false} label={({ name, percent }) => `${name}: ${((percent ?? 0) * 100).toFixed(0)}%`} outerRadius={100} dataKey={config.valueKey || "value"} nameKey={config.nameKey || "name"}>
                {config.data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );
      case "area":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={config.data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey={config.xKey} tick={axisStyle} />
              <YAxis tick={axisStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {config.yKeys?.map((key, i) => (
                <Area key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} fill={COLORS[i % COLORS.length]} fillOpacity={0.3} strokeWidth={2} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );
      default:
        return <DataTable data={config.data} />;
    }
  };

  return (
    <div className="my-2 p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      {chartTitle && <p className="text-sm font-medium mb-3">{chartTitle}</p>}
      {renderChart()}
    </div>
  );
}
