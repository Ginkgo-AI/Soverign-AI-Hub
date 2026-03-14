"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  enabled: boolean;
  requires_approval: boolean;
  source: string;
  created_at: string;
}

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    category: "plugin",
    handler_module: 'async def handle(**kwargs):\n    return {"result": "Hello from plugin"}',
    parameters_schema: "{}",
    requires_approval: true,
  });

  const fetchPlugins = useCallback(async () => {
    try {
      const data = await apiJson<{ plugins: Plugin[] }>("/api/plugins");
      setPlugins(data.plugins);
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const togglePlugin = async (plugin: Plugin) => {
    const action = plugin.enabled ? "disable" : "enable";
    await apiJson(`/api/plugins/${plugin.id}/${action}`, { method: "POST" });
    fetchPlugins();
  };

  const createPlugin = async () => {
    try {
      await apiJson("/api/plugins", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          category: form.category,
          handler_module: form.handler_module,
          parameters_schema: JSON.parse(form.parameters_schema),
          requires_approval: form.requires_approval,
        }),
      });
      setShowCreate(false);
      fetchPlugins();
    } catch (err) {
      alert(`Failed to create plugin: ${err}`);
    }
  };

  const deletePlugin = async (id: string) => {
    if (!confirm("Delete this plugin?")) return;
    await apiJson(`/api/plugins/${id}`, { method: "DELETE" });
    fetchPlugins();
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Tool Plugins</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Extend agent capabilities with custom tools
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-[var(--color-accent)] text-white rounded-lg text-sm hover:bg-[var(--color-accent-hover)]"
        >
          {showCreate ? "Cancel" : "Add Plugin"}
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] space-y-3">
          <input
            placeholder="Plugin name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-sm"
          />
          <input
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-sm"
          />
          <textarea
            placeholder="Handler source (Python)"
            value={form.handler_module}
            onChange={(e) => setForm({ ...form, handler_module: e.target.value })}
            rows={6}
            className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-sm font-mono"
          />
          <textarea
            placeholder='Parameters schema (JSON, e.g. {"type": "object", "properties": {}})'
            value={form.parameters_schema}
            onChange={(e) => setForm({ ...form, parameters_schema: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-sm font-mono"
          />
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.requires_approval}
                onChange={(e) => setForm({ ...form, requires_approval: e.target.checked })}
              />
              Requires approval
            </label>
            <button
              onClick={createPlugin}
              disabled={!form.name || !form.handler_module}
              className="px-4 py-2 bg-[var(--color-accent)] text-white rounded text-sm disabled:opacity-50"
            >
              Create Plugin
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>
      ) : plugins.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">No plugins installed yet.</p>
      ) : (
        <div className="space-y-2">
          {plugins.map((plugin) => (
            <div
              key={plugin.id}
              className="flex items-center justify-between p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{plugin.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-border)] text-[var(--color-text-muted)]">
                    v{plugin.version}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-border)] text-[var(--color-text-muted)]">
                    {plugin.category}
                  </span>
                </div>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">{plugin.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => togglePlugin(plugin)}
                  className={`px-3 py-1 rounded text-xs font-medium ${
                    plugin.enabled
                      ? "bg-green-500/20 text-green-400"
                      : "bg-[var(--color-border)] text-[var(--color-text-muted)]"
                  }`}
                >
                  {plugin.enabled ? "Enabled" : "Disabled"}
                </button>
                <button
                  onClick={() => deletePlugin(plugin.id)}
                  className="px-3 py-1 rounded text-xs text-red-400 hover:bg-red-500/20"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
