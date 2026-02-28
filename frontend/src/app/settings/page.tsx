"use client";

import { useState, useEffect, useCallback } from "react";
import { apiJson } from "@/lib/api";
import { getSystemHealth, type SystemHealth } from "@/lib/admin";

interface SystemPrompt {
  id: string;
  name: string;
  content: string;
  created_at: string;
}

interface BackendInfo {
  model: string;
  backend: string;
  status: string;
}

export default function SettingsPage() {
  const [tab, setTab] = useState<"prompts" | "backend" | "health" | "theme">("prompts");
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  const [backendInfo, setBackendInfo] = useState<BackendInfo | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  // New prompt form
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  // Theme
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const loadPrompts = useCallback(async () => {
    try {
      const data = await apiJson<{ prompts: SystemPrompt[] }>("/api/system-prompts");
      setPrompts(data.prompts);
    } catch {
      /* empty */
    }
  }, []);

  const loadBackendInfo = useCallback(async () => {
    try {
      const data = await apiJson<BackendInfo>("/api/chat/backend");
      setBackendInfo(data);
    } catch {
      /* empty */
    }
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      const data = await getSystemHealth();
      setHealth(data);
    } catch {
      /* empty */
    }
  }, []);

  useEffect(() => {
    Promise.all([loadPrompts(), loadBackendInfo(), loadHealth()]).finally(() =>
      setLoading(false)
    );
  }, [loadPrompts, loadBackendInfo, loadHealth]);

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiJson("/api/system-prompts", {
        method: "POST",
        body: JSON.stringify({ name: newName, content: newContent }),
      });
      setNewName("");
      setNewContent("");
      setShowCreate(false);
      loadPrompts();
    } catch {
      alert("Failed to create system prompt");
    }
  };

  const handleDeletePrompt = async (id: string) => {
    if (!confirm("Delete this system prompt?")) return;
    try {
      await apiJson(`/api/system-prompts/${id}`, { method: "DELETE" });
      loadPrompts();
    } catch {
      alert("Failed to delete prompt");
    }
  };

  const tabs = [
    { id: "prompts" as const, label: "System Prompts" },
    { id: "backend" as const, label: "LLM Backend" },
    { id: "health" as const, label: "Service Health" },
    { id: "theme" as const, label: "Appearance" },
  ];

  const healthStatusColor = (status: string) => {
    if (status === "healthy" || status === "ok" || status === "connected")
      return "text-green-400";
    if (status === "degraded" || status === "slow") return "text-yellow-400";
    return "text-red-400";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--color-text-muted)]">
        <p>Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Tab sidebar */}
      <div className="w-52 border-r border-[var(--color-border)] flex flex-col shrink-0">
        <div className="p-4 border-b border-[var(--color-border)]">
          <h2 className="text-lg font-semibold">Settings</h2>
        </div>
        <nav className="p-2 space-y-0.5">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                tab === t.id
                  ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl">
          {/* System Prompts */}
          {tab === "prompts" && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">System Prompts</h3>
                <button
                  onClick={() => setShowCreate(true)}
                  className="px-3 py-1.5 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
                >
                  + New Prompt
                </button>
              </div>

              {showCreate && (
                <form
                  onSubmit={handleCreatePrompt}
                  className="mb-4 p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] space-y-3"
                >
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Prompt name"
                    required
                    className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
                  />
                  <textarea
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    placeholder="Prompt content..."
                    required
                    rows={5}
                    className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)] resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      className="px-4 py-1.5 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
                    >
                      Create
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowCreate(false)}
                      className="px-4 py-1.5 text-xs border border-[var(--color-border)] rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {prompts.length === 0 ? (
                <p className="text-sm text-[var(--color-text-muted)]">
                  No system prompts configured.
                </p>
              ) : (
                <div className="space-y-2">
                  {prompts.map((p) => (
                    <div
                      key={p.id}
                      className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] group"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="text-sm font-medium">{p.name}</h4>
                          <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                            Created{" "}
                            {new Date(p.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <button
                          onClick={() => handleDeletePrompt(p.id)}
                          className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          Delete
                        </button>
                      </div>
                      <pre className="mt-2 text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] p-3 rounded-md whitespace-pre-wrap max-h-32 overflow-y-auto">
                        {p.content}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* LLM Backend */}
          {tab === "backend" && (
            <div>
              <h3 className="text-lg font-semibold mb-4">LLM Backend</h3>
              {backendInfo ? (
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                    <p className="text-xs text-[var(--color-text-muted)] mb-1">
                      Current Model
                    </p>
                    <p className="text-sm font-medium">{backendInfo.model}</p>
                  </div>
                  <div className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                    <p className="text-xs text-[var(--color-text-muted)] mb-1">
                      Backend
                    </p>
                    <p className="text-sm font-medium">{backendInfo.backend}</p>
                  </div>
                  <div className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                    <p className="text-xs text-[var(--color-text-muted)] mb-1">
                      Status
                    </p>
                    <p
                      className={`text-sm font-medium ${healthStatusColor(backendInfo.status)}`}
                    >
                      {backendInfo.status}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">
                  Could not load backend information.
                </p>
              )}
            </div>
          )}

          {/* Service Health */}
          {tab === "health" && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Service Health</h3>
                <button
                  onClick={loadHealth}
                  className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                >
                  Refresh
                </button>
              </div>
              {health ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 mb-4">
                    <span
                      className={`inline-block w-2.5 h-2.5 rounded-full ${
                        health.status === "healthy"
                          ? "bg-green-400"
                          : "bg-red-400"
                      }`}
                    />
                    <span className="text-sm font-medium capitalize">
                      {health.status}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {new Date(health.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(health.checks).map(([service, status]) => (
                      <div
                        key={service}
                        className="p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] flex items-center justify-between"
                      >
                        <span className="text-sm capitalize">
                          {service.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`text-xs font-medium ${healthStatusColor(status)}`}
                        >
                          {status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">
                  Could not load health status.
                </p>
              )}
            </div>
          )}

          {/* Appearance */}
          {tab === "theme" && (
            <div>
              <h3 className="text-lg font-semibold mb-4">Appearance</h3>
              <div className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <p className="text-sm mb-3">Theme</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setTheme("dark")}
                    className={`px-4 py-2 text-sm rounded-md transition-colors ${
                      theme === "dark"
                        ? "bg-[var(--color-accent)] text-white"
                        : "border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    Dark
                  </button>
                  <button
                    onClick={() => setTheme("light")}
                    className={`px-4 py-2 text-sm rounded-md transition-colors ${
                      theme === "light"
                        ? "bg-[var(--color-accent)] text-white"
                        : "border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    Light
                  </button>
                </div>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-2">
                  Light theme coming soon. Dark mode is the default.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
