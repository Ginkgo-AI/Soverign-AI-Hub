"use client";

import { useState, useEffect } from "react";
import { apiJson } from "@/lib/api";
import { getSystemHealth, fetchAuditLogs, type AuditEntry, type SystemHealth } from "@/lib/admin";
import {
  MessageSquare,
  Database,
  Bot,
  Boxes,
  FileText,
  Radio,
  Activity,
  Shield,
} from "lucide-react";

interface StatCard {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  href: string;
  color: string;
}

export default function AdminPage() {
  const [stats, setStats] = useState<StatCard[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [recentActivity, setRecentActivity] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const cards: StatCard[] = [];

      const results = await Promise.allSettled([
        apiJson<{ total: number }>("/api/conversations?page_size=1"),
        apiJson<{ total: number }>("/api/collections"),
        apiJson<{ total: number }>("/api/models"),
        apiJson<{ total: number }>("/api/agents"),
        apiJson<{ collections: Array<{ document_count?: number }> }>("/api/collections").then((cols) => {
          let docCount = 0;
          if (cols?.collections) {
            for (const c of cols.collections) {
              docCount += c.document_count || 0;
            }
          }
          return { total: docCount };
        }),
        apiJson<{ devices: unknown[] }>("/api/edge/devices").then((d) => ({
          total: Array.isArray(d.devices) ? d.devices.length : 0,
        })),
      ]);

      const labels = [
        { label: "Conversations", icon: <MessageSquare size={18} />, href: "/chat", color: "from-cyan-500 to-blue-500" },
        { label: "Collections", icon: <Database size={18} />, href: "/collections", color: "from-violet-500 to-purple-500" },
        { label: "Models", icon: <Boxes size={18} />, href: "/models", color: "from-blue-500 to-indigo-500" },
        { label: "Agents", icon: <Bot size={18} />, href: "/agents", color: "from-amber-500 to-orange-500" },
        { label: "Documents", icon: <FileText size={18} />, href: "/collections", color: "from-emerald-500 to-green-500" },
        { label: "Edge Devices", icon: <Radio size={18} />, href: "/admin/edge", color: "from-rose-500 to-pink-500" },
      ];

      labels.forEach((l, i) => {
        const result = results[i];
        cards.push({
          ...l,
          value:
            result.status === "fulfilled"
              ? (result.value as { total: number }).total
              : "-",
        });
      });

      setStats(cards);

      try {
        const h = await getSystemHealth();
        setHealth(h);
      } catch { /* empty */ }

      try {
        const audit = await fetchAuditLogs({ page_size: 5 });
        setRecentActivity(audit.entries);
      } catch { /* empty */ }

      setLoading(false);
    }
    load();
  }, []);

  const healthDot = (status: string) => {
    if (status === "healthy" || status === "ok" || status === "connected")
      return "bg-green-400";
    if (status === "degraded" || status === "slow") return "bg-yellow-400";
    return "bg-red-400";
  };

  return (
    <div className="h-full overflow-y-auto bg-mesh">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/10 flex items-center justify-center">
            <Shield size={20} className="text-violet-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Administration</h2>
            <p className="text-sm text-[var(--color-text-muted)]">System overview and health</p>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-10">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="glass-card p-5 h-28 shimmer" />
              ))
            : stats.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  className="glass-card gradient-border p-5 group cursor-pointer"
                >
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center mb-3 opacity-80 group-hover:opacity-100 transition-opacity`}>
                    <span className="text-white">{s.icon}</span>
                  </div>
                  <p className="text-2xl font-bold tabular-nums">{s.value}</p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{s.label}</p>
                </a>
              ))}
        </div>

        {/* Health + Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-10">
          <div className="glass-card p-6">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-green-500/20 to-emerald-500/10 flex items-center justify-center">
                <Activity size={16} className="text-green-400" />
              </div>
              <h3 className="text-sm font-semibold">System Health</h3>
              {health && (
                <span className={`inline-block w-2.5 h-2.5 rounded-full ml-auto ${healthDot(health.status)} ${health.status === "healthy" || health.status === "ok" ? "" : "animate-pulse"}`} />
              )}
            </div>
            {health ? (
              <div className="space-y-1">
                {Object.entries(health.checks).map(([service, status]) => (
                  <div key={service} className="flex items-center justify-between py-2 border-b border-white/[0.03] last:border-0">
                    <span className="text-sm capitalize text-[var(--color-text-muted)]">{service.replace(/_/g, " ")}</span>
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${healthDot(status)}`} />
                      <span className="text-sm">{status}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-muted)]">{loading ? "Loading..." : "Could not load health status"}</p>
            )}
          </div>

          <div className="glass-card p-6">
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/10 flex items-center justify-center">
                <FileText size={16} className="text-blue-400" />
              </div>
              <h3 className="text-sm font-semibold">Recent Activity</h3>
            </div>
            {recentActivity.length > 0 ? (
              <div className="space-y-1">
                {recentActivity.map((entry) => (
                  <div key={entry.id} className="flex items-start justify-between py-2 border-b border-white/[0.03] last:border-0">
                    <div>
                      <p className="text-sm font-medium">{entry.action}</p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        {entry.resource_type}
                        {entry.user_id && ` by ${entry.user_id.slice(0, 8)}...`}
                      </p>
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)] shrink-0">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-muted)]">{loading ? "Loading..." : "No recent activity"}</p>
            )}
          </div>
        </div>

        {/* Admin Links */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { href: "/admin/users", title: "Users", description: "Manage users and roles" },
            { href: "/admin/audit", title: "Audit Log", description: "View all system activity" },
            { href: "/admin/security", title: "Security", description: "Classification, encryption, air-gap" },
            { href: "/admin/compliance", title: "Compliance", description: "NIST 800-53 compliance dashboard" },
            { href: "/admin/plugins", title: "Plugins", description: "Manage installed plugins" },
            { href: "/admin/edge", title: "Edge Devices", description: "Manage connected edge nodes" },
          ].map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="glass-card gradient-border p-5 group cursor-pointer"
            >
              <h3 className="font-semibold text-sm mb-1 group-hover:text-white transition-colors">{link.title}</h3>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">{link.description}</p>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
