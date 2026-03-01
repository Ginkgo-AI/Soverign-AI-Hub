"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  listModels,
  deleteModel,
  scanModels,
  type Model,
  type ModelListResponse,
  type ModelScanResult,
} from "@/lib/models";
import { apiJson } from "@/lib/api";
import {
  Cpu,
  HardDrive,
  Monitor,
  Loader2,
  ChevronDown,
  AlertCircle,
  Check,
  X,
} from "lucide-react";

/* ── Types from model-management API ── */

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

/* ── Constants ── */

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

const STATUS_COLORS: Record<string, string> = {
  loaded: "bg-[var(--color-success)]/20 text-[var(--color-success)]",
  available: "bg-blue-500/20 text-blue-400",
  downloading: "bg-yellow-500/20 text-yellow-400",
  error: "bg-[var(--color-danger)]/20 text-[var(--color-danger)]",
};

const BACKEND_LABELS: Record<string, string> = {
  vllm: "vLLM (GPU)",
  "llama-cpp": "llama.cpp (CPU)",
};

/* ── Detail modal (unchanged) ── */

function ModelDetailModal({
  model,
  onClose,
}: {
  model: Model;
  onClose: () => void;
}) {
  const params = model.parameters || {};
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 max-w-xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">{model.name}</h3>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-xl">
            x
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <span className="text-[var(--color-text-muted)]">Status</span>
            <span className={`px-2 py-0.5 rounded text-xs w-fit ${STATUS_COLORS[model.status] || ""}`}>
              {model.status}
            </span>
            <span className="text-[var(--color-text-muted)]">Backend</span>
            <span>{BACKEND_LABELS[model.backend] || model.backend}</span>
            <span className="text-[var(--color-text-muted)]">Version</span>
            <span>{model.version}</span>
            <span className="text-[var(--color-text-muted)]">Quantization</span>
            <span>{model.quantization || "None"}</span>
            <span className="text-[var(--color-text-muted)]">File Path</span>
            <span className="break-all font-mono text-xs">{model.file_path}</span>
          </div>

          {params.param_count ? (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Parameters</span>
              <span>{String(params.param_count)}</span>
            </div>
          ) : null}
          {params.context_window ? (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Context Window</span>
              <span>{String(params.context_window)} tokens</span>
            </div>
          ) : null}
          {params.file_size ? (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">File Size</span>
              <span>{(Number(params.file_size) / (1024 * 1024 * 1024)).toFixed(2)} GB</span>
            </div>
          ) : null}
          {params.features && Array.isArray(params.features) ? (
            <div>
              <span className="text-[var(--color-text-muted)] block mb-1">Features</span>
              <div className="flex gap-1 flex-wrap">
                {(params.features as string[]).map((f) => (
                  <span key={f} className="px-2 py-0.5 text-xs rounded bg-[var(--color-border)]">{f}</span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="text-[var(--color-text-muted)] text-xs mt-4">
            Created: {new Date(model.created_at).toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main page ── */

export default function ModelsPage() {
  /* Registry model list (existing) */
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterBackend, setFilterBackend] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [scanning, setScanning] = useState(false);

  /* Model-management state */
  const [mgmtModels, setMgmtModels] = useState<ModelInfo[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendedModel[]>([]);
  const [resources, setResources] = useState<SystemResources | null>(null);
  const [activeModel, setActiveModel] = useState("");
  const [activeBackend, setActiveBackend] = useState("vllm");
  const [contextLength, setContextLength] = useState(8192);
  const [keepAlive, setKeepAlive] = useState("5m");
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [mgmtError, setMgmtError] = useState<string | null>(null);
  const [mgmtSuccess, setMgmtSuccess] = useState<string | null>(null);

  const showSuccess = (msg: string) => {
    setMgmtSuccess(msg);
    setMgmtError(null);
    setTimeout(() => setMgmtSuccess(null), 3000);
  };

  /* ── Fetch registry models ── */
  const fetchModels = () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filterBackend) params.backend = filterBackend;
    if (filterStatus) params.status = filterStatus;

    listModels(params)
      .then((res: ModelListResponse) => {
        setModels(res.models || []);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchModels();
  }, [filterBackend, filterStatus]);

  /* ── Fetch management data (resources, available models, recommendations) ── */
  const fetchMgmtData = useCallback(async () => {
    try {
      const [modelsRes, resourcesRes, recsRes] = await Promise.allSettled([
        apiJson<{ models: ModelInfo[] }>("/api/model-management/available"),
        apiJson<SystemResources>("/api/model-management/system-resources"),
        apiJson<{ models: RecommendedModel[] }>("/api/model-management/recommended"),
      ]);

      if (modelsRes.status === "fulfilled") setMgmtModels(modelsRes.value.models);
      if (resourcesRes.status === "fulfilled") setResources(resourcesRes.value);
      if (recsRes.status === "fulfilled") setRecommendations(recsRes.value.models);

      const failures = [modelsRes, resourcesRes, recsRes].filter(
        (r) => r.status === "rejected"
      );
      if (failures.length === 3) {
        setMgmtError("Could not connect to model backends. Is the gateway running?");
      } else if (failures.length > 0) {
        console.warn("Some model management calls failed:", failures.map((f) => (f as PromiseRejectedResult).reason));
      }
    } catch (e) {
      setMgmtError(`Unexpected error loading model data: ${e instanceof Error ? e.message : e}`);
    }
  }, []);

  useEffect(() => {
    fetchMgmtData();
  }, [fetchMgmtData]);

  /* ── Actions ── */
  const handleLoad = async (model: string, backend: string) => {
    setActionLoading(model);
    setMgmtError(null);
    try {
      await apiJson("/api/model-management/load", {
        method: "POST",
        body: JSON.stringify({ model, backend, keep_alive: keepAlive }),
      });
      showSuccess(`Model "${model}" loaded successfully`);
      await fetchMgmtData();
      fetchModels();
    } catch (e) {
      setMgmtError(`Failed to load "${model}": ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnload = async (model: string, backend: string) => {
    setActionLoading(model);
    setMgmtError(null);
    try {
      await apiJson("/api/model-management/unload", {
        method: "POST",
        body: JSON.stringify({ model, backend }),
      });
      showSuccess(`Model "${model}" unloaded`);
      await fetchMgmtData();
      fetchModels();
    } catch (e) {
      setMgmtError(`Failed to unload "${model}": ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleApplyConfig = async () => {
    setMgmtError(null);
    try {
      await apiJson("/api/model-management/config", {
        method: "PATCH",
        body: JSON.stringify({
          model: activeModel,
          backend: activeBackend,
          context_length: contextLength,
          keep_alive: keepAlive,
        }),
      });
      showSuccess("Configuration applied");
    } catch (e) {
      setMgmtError(`Failed to apply configuration: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this model from the registry?")) return;
    try {
      await deleteModel(id);
      fetchModels();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      alert(msg);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      const result: ModelScanResult = await scanModels();
      alert(`Scan complete: ${result.discovered} models discovered and registered.`);
      fetchModels();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Scan failed";
      alert(msg);
    } finally {
      setScanning(false);
    }
  };

  const filtered = models.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.quantization || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold">Models</h2>
        <div className="flex gap-2">
          <Link
            href="/models/training"
            className="px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90"
          >
            Fine-Tuning
          </Link>
          <Link
            href="/models/evaluation"
            className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)]"
          >
            Evaluation
          </Link>
          <Link
            href="/models/datasets"
            className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)]"
          >
            Datasets
          </Link>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-4 py-2 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)] disabled:opacity-50"
          >
            {scanning ? "Scanning..." : "Scan Directory"}
          </button>
        </div>
      </div>

      {/* ── Management banners ── */}
      {mgmtError && (
        <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 mb-4">
          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
          <span>{mgmtError}</span>
          <button onClick={() => setMgmtError(null)} className="ml-auto flex-shrink-0">
            <X size={12} />
          </button>
        </div>
      )}
      {mgmtSuccess && (
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-500/10 border border-green-500/20 text-xs text-green-400 mb-4">
          <Check size={14} className="flex-shrink-0" />
          <span>{mgmtSuccess}</span>
        </div>
      )}

      {/* ── System Resources + Active Model Config ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* System Resources */}
        <div className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
            System Resources
          </label>
          {resources ? (
            <div className="mt-3 space-y-3">
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
                  <div className="h-1.5 rounded-full bg-[var(--color-bg)] overflow-hidden">
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
                  <div className="h-1.5 rounded-full bg-[var(--color-bg)] overflow-hidden">
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
                    <div className="h-1.5 rounded-full bg-[var(--color-bg)] overflow-hidden">
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
          ) : (
            <div className="mt-3 flex items-center justify-center py-6">
              <Loader2 className="animate-spin text-[var(--color-text-muted)]" size={20} />
            </div>
          )}
        </div>

        {/* Active Model Configuration */}
        <div className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
            Active Model Configuration
          </label>

          {/* Model selector dropdown */}
          <div className="relative mt-3">
            <button
              onClick={() => setShowModelDropdown(!showModelDropdown)}
              className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] transition-colors text-sm text-left"
            >
              <span className="flex items-center gap-2 truncate">
                {activeModel && mgmtModels.some((m) => m.id === activeModel) && (
                  <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                )}
                {activeModel || "Auto (default model)"}
              </span>
              <ChevronDown size={14} className="flex-shrink-0 text-[var(--color-text-muted)]" />
            </button>

            {showModelDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg z-10">
                <button
                  onClick={() => {
                    setActiveModel("");
                    setActiveBackend("vllm");
                    setShowModelDropdown(false);
                  }}
                  className="w-full px-3 py-2 text-sm text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  Auto (default model)
                </button>
                {mgmtModels.map((m) => (
                  <button
                    key={`${m.backend}:${m.id}`}
                    onClick={() => {
                      setActiveModel(m.id);
                      setActiveBackend(m.backend);
                      setShowModelDropdown(false);
                    }}
                    className={`w-full px-3 py-2 text-sm text-left hover:bg-[var(--color-surface-hover)] transition-colors flex items-center justify-between gap-2 ${
                      activeModel === m.id ? "bg-[var(--color-accent)]/10" : ""
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
          {activeModel && (() => {
            const m = mgmtModels.find((m) => m.id === activeModel);
            if (!m) return null;
            return (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {m.family && (
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                    {m.family}
                  </span>
                )}
                {m.parameter_count && (
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                    {m.parameter_count}
                  </span>
                )}
                {m.context_length && (
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                    ctx: {(m.context_length / 1024).toFixed(0)}K
                  </span>
                )}
              </div>
            );
          })()}

          {/* Load/Unload for active model */}
          {activeModel && (
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => handleLoad(activeModel, activeBackend)}
                disabled={actionLoading !== null}
                className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white disabled:opacity-50 transition-colors"
              >
                {actionLoading === activeModel ? (
                  <Loader2 size={14} className="animate-spin mx-auto" />
                ) : (
                  "Load"
                )}
              </button>
              <button
                onClick={() => handleUnload(activeModel, activeBackend)}
                disabled={actionLoading !== null}
                className="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] disabled:opacity-50 transition-colors"
              >
                Unload
              </button>
            </div>
          )}

          {/* Context Length */}
          <div className="mt-4">
            <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
              Context Length
            </label>
            <div className="mt-2 grid grid-cols-4 gap-1.5">
              {CONTEXT_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setContextLength(preset.value)}
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
          </div>

          {/* Keep Alive */}
          <div className="mt-4">
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
          </div>

          {/* Apply button */}
          <button
            onClick={handleApplyConfig}
            className="w-full mt-4 py-2.5 text-sm font-medium rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white transition-colors"
          >
            Apply Configuration
          </button>
        </div>
      </div>

      {/* ── Recommended Models ── */}
      {recommendations.length > 0 && (
        <div className="mb-6">
          <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
            Recommended Models
          </label>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {recommendations.map((rec) => {
              const fit = FIT_STYLES[rec.fit] || FIT_STYLES.unknown;
              return (
                <button
                  key={`${rec.backend}:${rec.id}`}
                  onClick={() => {
                    setActiveModel(rec.id);
                    setActiveBackend(rec.backend);
                  }}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] transition-colors text-left ${
                    activeModel === rec.id ? "border-[var(--color-accent)]" : ""
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
        </div>
      )}

      {/* ── Search and filters ── */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="Search models..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
        />
        <select
          value={filterBackend}
          onChange={(e) => setFilterBackend(e.target.value)}
          className="px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
        >
          <option value="">All Backends</option>
          <option value="vllm">vLLM (GPU)</option>
          <option value="llama-cpp">llama.cpp (CPU)</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
        >
          <option value="">All Statuses</option>
          <option value="available">Available</option>
          <option value="loaded">Loaded</option>
          <option value="downloading">Downloading</option>
          <option value="error">Error</option>
        </select>
      </div>

      {loading && <p className="text-[var(--color-text-muted)]">Loading models...</p>}
      {error && <p className="text-[var(--color-danger)]">Error: {error}</p>}

      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <p className="text-lg mb-2">No models found</p>
          <p className="text-sm">
            Register models manually, scan the /models directory, or download from HuggingFace.
          </p>
        </div>
      )}

      {/* ── Model cards grid ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((model) => {
          const params = model.parameters || {};
          // Find matching mgmt model for load/unload
          const mgmt = mgmtModels.find((m) => m.id === model.name);
          return (
            <div
              key={model.id}
              className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate">{model.name}</h3>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                    {BACKEND_LABELS[model.backend] || model.backend}
                  </p>
                </div>
                <span className={`px-2 py-0.5 text-xs rounded shrink-0 ml-2 ${STATUS_COLORS[model.status] || ""}`}>
                  {model.status}
                </span>
              </div>

              <div className="flex flex-wrap gap-1 mb-3 text-xs">
                {model.quantization ? (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{model.quantization}</span>
                ) : null}
                {params.param_count ? (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{String(params.param_count)}</span>
                ) : null}
                {params.context_window ? (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{String(params.context_window)} ctx</span>
                ) : null}
              </div>

              <div className="flex gap-2 text-xs">
                <button
                  onClick={() => handleLoad(model.name, model.backend)}
                  disabled={actionLoading !== null}
                  className="px-3 py-1.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/30 transition-colors disabled:opacity-50"
                >
                  {actionLoading === model.name ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    "Load"
                  )}
                </button>
                {mgmt?.loaded && (
                  <button
                    onClick={() => handleUnload(model.name, model.backend)}
                    disabled={actionLoading !== null}
                    className="px-3 py-1.5 rounded bg-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                  >
                    Unload
                  </button>
                )}
                <button
                  onClick={() => setSelectedModel(model)}
                  className="px-3 py-1.5 rounded bg-[var(--color-border)] hover:bg-[var(--color-primary)]/20 transition-colors"
                >
                  Details
                </button>
                <button
                  onClick={() => handleDelete(model.id)}
                  className="px-3 py-1.5 rounded text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {selectedModel && (
        <ModelDetailModal model={selectedModel} onClose={() => setSelectedModel(null)} />
      )}
    </div>
  );
}
