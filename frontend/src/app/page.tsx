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
} from "lucide-react";

interface StatCard {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  href: string;
}

export default function Home() {
  const [stats, setStats] = useState<StatCard[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [recentActivity, setRecentActivity] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const cards: StatCard[] = [];

      // Fetch counts in parallel, gracefully handle failures
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
        { label: "Conversations", icon: <MessageSquare size={20} />, href: "/chat" },
        { label: "Collections", icon: <Database size={20} />, href: "/collections" },
        { label: "Models", icon: <Boxes size={20} />, href: "/models" },
        { label: "Agents", icon: <Bot size={20} />, href: "/agents" },
        { label: "Documents", icon: <FileText size={20} />, href: "/collections" },
        { label: "Edge Devices", icon: <Radio size={20} />, href: "/admin/edge" },
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

      // Health
      try {
        const h = await getSystemHealth();
        setHealth(h);
      } catch {
        /* empty */
      }

      // Recent audit entries
      try {
        const audit = await fetchAuditLogs({ page_size: 5 });
        setRecentActivity(audit.entries);
      } catch {
        /* empty */
      }

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
    <div className="h-full overflow-y-auto bg-gradient-subtle">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold">Sovereign AI Hub</h2>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Enterprise AI capabilities with zero data exfiltration
          </p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] animate-pulse h-24"
                />
              ))
            : stats.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] card-glow transition-all"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[var(--color-text-muted)] opacity-70">
                      {s.icon}
                    </span>
                  </div>
                  <p className="text-2xl font-bold">{s.value}</p>
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                    {s.label}
                  </p>
                </a>
              ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System Health */}
          <div className="p-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={16} className="text-[var(--color-text-muted)]" />
              <h3 className="text-sm font-semibold">System Health</h3>
              {health && (
                <span
                  className={`inline-block w-2 h-2 rounded-full ml-auto ${healthDot(health.status)}`}
                />
              )}
            </div>
            {health ? (
              <div className="space-y-2">
                {Object.entries(health.checks).map(([service, status]) => (
                  <div
                    key={service}
                    className="flex items-center justify-between py-1.5"
                  >
                    <span className="text-xs capitalize text-[var(--color-text-muted)]">
                      {service.replace(/_/g, " ")}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full ${healthDot(status)}`}
                      />
                      <span className="text-xs">{status}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--color-text-muted)]">
                {loading ? "Loading..." : "Could not load health status"}
              </p>
            )}
          </div>

          {/* Recent Activity */}
          <div className="p-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center gap-2 mb-4">
              <FileText size={16} className="text-[var(--color-text-muted)]" />
              <h3 className="text-sm font-semibold">Recent Activity</h3>
            </div>
            {recentActivity.length > 0 ? (
              <div className="space-y-2">
                {recentActivity.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-start justify-between py-1.5 border-b border-[var(--color-border)] last:border-0"
                  >
                    <div>
                      <p className="text-xs font-medium">{entry.action}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">
                        {entry.resource_type}
                        {entry.user_id && ` by ${entry.user_id.slice(0, 8)}...`}
                      </p>
                    </div>
                    <span className="text-[10px] text-[var(--color-text-muted)] shrink-0">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--color-text-muted)]">
                {loading ? "Loading..." : "No recent activity"}
              </p>
            )}
          </div>
        </div>

        {/* Quick links */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
          <QuickLink
            href="/chat"
            title="Chat"
            description="Multi-turn conversations with local LLMs"
          />
          <QuickLink
            href="/collections"
            title="Knowledge Base"
            description="Upload documents and search with RAG"
          />
          <QuickLink
            href="/agents"
            title="Agents"
            description="Autonomous task execution with tools"
          />
          <QuickLink
            href="/models"
            title="Models"
            description="Manage, evaluate, and fine-tune"
          />
        </div>
      </div>
    </div>
  );
}

function QuickLink({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <a
      href={href}
      className="block p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] card-glow transition-all text-left"
    >
      <h3 className="font-semibold text-sm mb-1">{title}</h3>
      <p className="text-[10px] text-[var(--color-text-muted)]">
        {description}
      </p>
    </a>
  );
}
