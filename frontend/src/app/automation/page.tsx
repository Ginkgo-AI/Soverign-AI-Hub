"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface Schedule {
  id: string;
  name: string;
  cron_expression: string;
  agent_id: string;
  prompt: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
}

interface WatcherItem {
  id: string;
  name: string;
  watch_path: string;
  file_pattern: string;
  action_type: string;
  enabled: boolean;
}

interface AutoLog {
  id: string;
  trigger_type: string;
  status: string;
  created_at: string;
  details: Record<string, unknown> | null;
}

type Tab = "schedules" | "watchers" | "logs";

export default function AutomationPage() {
  const [tab, setTab] = useState<Tab>("schedules");
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [watchers, setWatchers] = useState<WatcherItem[]>([]);
  const [logs, setLogs] = useState<AutoLog[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "schedules") {
        const data = await apiJson<{ schedules: Schedule[] }>("/api/automation/schedules");
        setSchedules(data.schedules);
      } else if (tab === "watchers") {
        const data = await apiJson<{ watchers: WatcherItem[] }>("/api/automation/watchers");
        setWatchers(data.watchers);
      } else {
        const data = await apiJson<{ logs: AutoLog[] }>("/api/automation/logs");
        setLogs(data.logs);
      }
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const triggerSchedule = async (id: string) => {
    await apiJson(`/api/automation/schedules/${id}/trigger`, { method: "POST" });
    fetchData();
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Automation</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Schedules, file watchers, and automation logs
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[var(--color-surface)] rounded-lg p-1 w-fit">
        {(["schedules", "watchers", "logs"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "bg-[var(--color-accent)] text-white"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>
      ) : tab === "schedules" ? (
        <div className="space-y-2">
          {schedules.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">No schedules configured.</p>
          ) : (
            schedules.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{s.name}</span>
                    <code className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]">
                      {s.cron_expression}
                    </code>
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1 truncate max-w-md">{s.prompt}</p>
                  {s.last_run_at && (
                    <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                      Last run: {new Date(s.last_run_at).toLocaleString()} — {s.last_status}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded ${s.enabled ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"}`}>
                    {s.enabled ? "Active" : "Paused"}
                  </span>
                  <button
                    onClick={() => triggerSchedule(s.id)}
                    className="px-3 py-1 rounded text-xs bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
                  >
                    Run Now
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : tab === "watchers" ? (
        <div className="space-y-2">
          {watchers.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">No file watchers configured.</p>
          ) : (
            watchers.map((w) => (
              <div key={w.id} className="flex items-center justify-between p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <div>
                  <span className="font-medium text-sm">{w.name}</span>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">
                    {w.watch_path} — {w.file_pattern} — {w.action_type}
                  </p>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded ${w.enabled ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"}`}>
                  {w.enabled ? "Active" : "Paused"}
                </span>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {logs.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">No automation logs yet.</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <div className="flex items-center gap-3">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-border)] capitalize">{log.trigger_type}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${log.status === "success" || log.status === "completed" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                    {log.status}
                  </span>
                </div>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  {new Date(log.created_at).toLocaleString()}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
