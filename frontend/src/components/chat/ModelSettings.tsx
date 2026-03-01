"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";
import {
  X,
  Cpu,
  HardDrive,
  Monitor,
  Loader2,
  ChevronDown,
  Zap,
  AlertCircle,
  Check,
} from "lucide-react";

interface ModelInfo {
  id: string;
  backend: string;
  size_bytes: number | null;
  parameter_count: string | null;
  quantization: string | null;
  family: string | null;
  loaded: boolean;
  context_length: number | null;
}

interface RecommendedModel extends ModelInfo {
  estimated_memory_gb: number | null;
  fit: "good" | "moderate" | "poor" | "unknown";
  fit_score: number;
}

interface SystemResources {
  ram_total_gb: number;
  ram_used_gb: number;
  ram_available_gb: number;
  ram_percent: number;
  cpu_count: number;
  cpu_percent: number;
  gpu_detected: boolean;
  gpu_name: string | null;
  gpu_memory_total_gb: number | null;
  gpu_memory_used_gb: number | null;
}

const CONTEXT_PRESETS = [
  { label: "2K", value: 2048 },
  { label: "4K", value: 4096 },
  { label: "8K", value: 8192 },
  { label: "16K", value: 16384 },
  { label: "32K", value: 32768 },
  { label: "64K", value: 65536 },
  { label: "128K", value: 131072 },
];

const KEEP_ALIVE_OPTIONS = [
  { label: "5 min", value: "5m" },
  { label: "30 min", value: "30m" },
  { label: "1 hour", value: "1h" },
  { label: "4 hours", value: "4h" },
  { label: "Forever", value: "-1" },
  { label: "Unload now", value: "0" },
];

const FIT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  good: { bg: "bg-green-500/15", text: "text-green-400", label: "Good fit" },
  moderate: { bg: "bg-yellow-500/15", text: "text-yellow-400", label: "Moderate" },
  poor: { bg: "bg-red-500/15", text: "text-red-400", label: "Poor fit" },
  unknown: { bg: "bg-gray-500/15", text: "text-gray-400", label: "Unknown" },
};

interface ModelSettingsProps {
  open: boolean;
  onClose: () => void;
  selectedModel: string;
  selectedBackend: string;
  onModelChange: (model: string, backend: string) => void;
  contextLength: number;
  onContextLengthChange: (len: number) => void;
}

export function ModelSettings({
  open,
  onClose,
  selectedModel,
  selectedBackend,
  onModelChange,
  contextLength,
  onContextLengthChange,
}: ModelSettingsProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendedModel[]>([]);
  const [resources, setResources] = useState<SystemResources | null>(null);
  const [keepAlive, setKeepAlive] = useState("5m");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 3000);
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelsRes, resourcesRes, recsRes] = await Promise.allSettled([
        apiJson<{ models: ModelInfo[] }>("/api/model-management/available"),
        apiJson<SystemResources>("/api/model-management/system-resources"),
        apiJson<{ models: RecommendedModel[] }>("/api/model-management/recommended"),
      ]);

      if (modelsRes.status === "fulfilled") setModels(modelsRes.value.models);
      if (resourcesRes.status === "fulfilled") setResources(resourcesRes.value);
      if (recsRes.status === "fulfilled") setRecommendations(recsRes.value.models);

      const failures = [modelsRes, resourcesRes, recsRes].filter(
        (r) => r.status === "rejected"
      );
      if (failures.length === 3) {
        setError("Could not connect to model backends. Is the gateway running?");
      } else if (failures.length > 0) {
        console.warn("Some model management calls failed:", failures.map((f) => (f as PromiseRejectedResult).reason));
      }
    } catch (e) {
      setError(`Unexpected error loading model settings: ${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchData();
  }, [open, fetchData]);

  const handleLoad = async (model: string, backend: string) => {
    setActionLoading(model);
    setError(null);
    try {
      await apiJson("/api/model-management/load", {
        method: "POST",
        body: JSON.stringify({ model, backend, keep_alive: keepAlive }),
      });
      showSuccess(`Model "${model}" loaded successfully`);
      await fetchData();
    } catch (e) {
      setError(`Failed to load "${model}": ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnload = async (model: string, backend: string) => {
    setActionLoading(model);
    setError(null);
    try {
      await apiJson("/api/model-management/unload", {
        method: "POST",
        body: JSON.stringify({ model, backend }),
      });
      showSuccess(`Model "${model}" unloaded`);
      await fetchData();
    } catch (e) {
      setError(`Failed to unload "${model}": ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleApplyConfig = async () => {
    setError(null);
    try {
      await apiJson("/api/model-management/config", {
        method: "PATCH",
        body: JSON.stringify({
          model: selectedModel,
          backend: selectedBackend,
          context_length: contextLength,
          keep_alive: keepAlive,
        }),
      });
      showSuccess("Configuration applied");
    } catch (e) {
      setError(`Failed to apply configuration: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-[420px] max-w-full bg-[var(--color-bg)] border-l border-[var(--color-border)] z-50 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2">
            <Zap size={18} className="text-[var(--color-accent)]" />
            <h2 className="text-sm font-semibold">Model Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
              <button onClick={() => setError(null)} className="ml-auto flex-shrink-0">
                <X size={12} />
              </button>
            </div>
          )}

          {/* Success banner */}
          {success && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-500/10 border border-green-500/20 text-xs text-green-400">
              <Check size={14} className="flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {loading && models.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-[var(--color-text-muted)]" size={24} />
            </div>
          ) : (
            <>
              {/* Model Selector */}
              <section>
                <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                  Active Model
                </label>
                <div className="relative mt-2">
                  <button
                    onClick={() => setShowModelDropdown(!showModelDropdown)}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] transition-colors text-sm text-left"
                  >
                    <span className="flex items-center gap-2 truncate">
                      {selectedModel && models.some((m) => m.id === selectedModel) && (
                        <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                      )}
                      {selectedModel || "Auto (default model)"}
                    </span>
                    <ChevronDown size={14} className="flex-shrink-0 text-[var(--color-text-muted)]" />
                  </button>

                  {showModelDropdown && (
                    <div className="absolute top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg z-10">
                      <button
                        onClick={() => {
                          onModelChange("", "vllm");
                          setShowModelDropdown(false);
                        }}
                        className="w-full px-3 py-2 text-sm text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                      >
                        Auto (default model)
                      </button>
                      {models.map((m) => (
                        <button
                          key={`${m.backend}:${m.id}`}
                          onClick={() => {
                            onModelChange(m.id, m.backend);
                            setShowModelDropdown(false);
                          }}
                          className={`w-full px-3 py-2 text-sm text-left hover:bg-[var(--color-surface-hover)] transition-colors flex items-center justify-between gap-2 ${
                            selectedModel === m.id ? "bg-[var(--color-accent)]/10" : ""
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${m.loaded ? "bg-green-400" : "bg-gray-500"}`} />
                            <span className="truncate">{m.id}</span>
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {m.quantization && (
                              <span className="px-1.5 py-0.5 text-[10px] rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
                                {m.quantization}
                              </span>
                            )}
                            <span className="text-[10px] text-[var(--color-text-muted)]">
                              {m.backend}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Model metadata */}
                {selectedModel && (() => {
                  const m = models.find((m) => m.id === selectedModel);
                  if (!m) return null;
                  return (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.family && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                          {m.family}
                        </span>
                      )}
                      {m.parameter_count && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                          {m.parameter_count}
                        </span>
                      )}
                      {m.context_length && (
                        <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                          ctx: {(m.context_length / 1024).toFixed(0)}K
                        </span>
                      )}
                    </div>
                  );
                })()}
              </section>

              {/* Load/Unload */}
              {selectedModel && (
                <section>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    Model Control
                  </label>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => handleLoad(selectedModel, selectedBackend)}
                      disabled={actionLoading !== null}
                      className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white disabled:opacity-50 transition-colors"
                    >
                      {actionLoading === selectedModel ? (
                        <Loader2 size={14} className="animate-spin mx-auto" />
                      ) : (
                        "Load"
                      )}
                    </button>
                    <button
                      onClick={() => handleUnload(selectedModel, selectedBackend)}
                      disabled={actionLoading !== null}
                      className="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] disabled:opacity-50 transition-colors"
                    >
                      Unload
                    </button>
                  </div>
                </section>
              )}

              {/* Context Length */}
              <section>
                <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                  Context Length
                </label>
                <div className="mt-2 grid grid-cols-4 gap-1.5">
                  {CONTEXT_PRESETS.map((preset) => (
                    <button
                      key={preset.value}
                      onClick={() => onContextLengthChange(preset.value)}
                      className={`px-2 py-1.5 text-xs rounded-lg border transition-colors ${
                        contextLength === preset.value
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium"
                          : "border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </section>

              {/* Keep Alive */}
              <section>
                <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                  Keep Alive
                </label>
                <div className="mt-2 grid grid-cols-3 gap-1.5">
                  {KEEP_ALIVE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setKeepAlive(opt.value)}
                      className={`px-2 py-1.5 text-xs rounded-lg border transition-colors ${
                        keepAlive === opt.value
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium"
                          : "border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </section>

              {/* Apply button */}
              <button
                onClick={handleApplyConfig}
                className="w-full py-2.5 text-sm font-medium rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white transition-colors"
              >
                Apply Configuration
              </button>

              {/* System Resources */}
              {resources && (
                <section>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    System Resources
                  </label>
                  <div className="mt-2 space-y-3">
                    {/* RAM */}
                    <div className="flex items-center gap-3">
                      <HardDrive size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span>RAM</span>
                          <span className="text-[var(--color-text-muted)]">
                            {resources.ram_used_gb.toFixed(1)} / {resources.ram_total_gb.toFixed(1)} GB
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[var(--color-surface)] overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              resources.ram_percent > 85
                                ? "bg-red-500"
                                : resources.ram_percent > 65
                                  ? "bg-yellow-500"
                                  : "bg-green-500"
                            }`}
                            style={{ width: `${Math.min(resources.ram_percent, 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* CPU */}
                    <div className="flex items-center gap-3">
                      <Cpu size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span>CPU ({resources.cpu_count} cores)</span>
                          <span className="text-[var(--color-text-muted)]">
                            {resources.cpu_percent.toFixed(0)}%
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[var(--color-surface)] overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              resources.cpu_percent > 85
                                ? "bg-red-500"
                                : resources.cpu_percent > 65
                                  ? "bg-yellow-500"
                                  : "bg-green-500"
                            }`}
                            style={{ width: `${Math.min(resources.cpu_percent, 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* GPU */}
                    {resources.gpu_detected && resources.gpu_memory_total_gb && (
                      <div className="flex items-center gap-3">
                        <Monitor size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="truncate">{resources.gpu_name || "GPU"}</span>
                            <span className="text-[var(--color-text-muted)] flex-shrink-0">
                              {resources.gpu_memory_used_gb?.toFixed(1)} / {resources.gpu_memory_total_gb.toFixed(1)} GB
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-[var(--color-surface)] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-purple-500 transition-all"
                              style={{
                                width: `${Math.min(
                                  ((resources.gpu_memory_used_gb || 0) / resources.gpu_memory_total_gb) * 100,
                                  100
                                )}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {!resources.gpu_detected && (
                      <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)]">
                        <Monitor size={14} className="flex-shrink-0" />
                        <span>No GPU detected — models will use CPU</span>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Recommended Models */}
              {recommendations.length > 0 && (
                <section>
                  <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    Recommended Models
                  </label>
                  <div className="mt-2 space-y-1.5">
                    {recommendations.map((rec) => {
                      const fit = FIT_STYLES[rec.fit] || FIT_STYLES.unknown;
                      return (
                        <button
                          key={`${rec.backend}:${rec.id}`}
                          onClick={() => onModelChange(rec.id, rec.backend)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-left ${
                            selectedModel === rec.id ? "border-[var(--color-accent)]" : ""
                          }`}
                        >
                          <div className="min-w-0">
                            <div className="text-xs font-medium truncate">{rec.id}</div>
                            <div className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-1.5 mt-0.5">
                              {rec.parameter_count && <span>{rec.parameter_count}</span>}
                              {rec.estimated_memory_gb && (
                                <span>~{rec.estimated_memory_gb} GB</span>
                              )}
                              <span>{rec.backend}</span>
                            </div>
                          </div>
                          <span
                            className={`px-2 py-0.5 text-[10px] font-medium rounded-full flex-shrink-0 ${fit.bg} ${fit.text}`}
                          >
                            {fit.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
