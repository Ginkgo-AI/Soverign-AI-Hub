"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listModels,
  deleteModel,
  scanModels,
  type Model,
  type ModelListResponse,
  type ModelScanResult,
} from "@/lib/models";

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

          {params.param_count && (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Parameters</span>
              <span>{String(params.param_count)}</span>
            </div>
          )}
          {params.context_window && (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Context Window</span>
              <span>{String(params.context_window)} tokens</span>
            </div>
          )}
          {params.file_size && (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">File Size</span>
              <span>{(Number(params.file_size) / (1024 * 1024 * 1024)).toFixed(2)} GB</span>
            </div>
          )}
          {params.features && Array.isArray(params.features) && (
            <div>
              <span className="text-[var(--color-text-muted)] block mb-1">Features</span>
              <div className="flex gap-1 flex-wrap">
                {(params.features as string[]).map((f) => (
                  <span key={f} className="px-2 py-0.5 text-xs rounded bg-[var(--color-border)]">{f}</span>
                ))}
              </div>
            </div>
          )}

          <div className="text-[var(--color-text-muted)] text-xs mt-4">
            Created: {new Date(model.created_at).toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterBackend, setFilterBackend] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [scanning, setScanning] = useState(false);

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

      {/* Search and filters */}
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

      {/* Model cards grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((model) => {
          const params = model.parameters || {};
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
                {model.quantization && (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{model.quantization}</span>
                )}
                {params.param_count && (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{String(params.param_count)}</span>
                )}
                {params.context_window && (
                  <span className="px-2 py-0.5 rounded bg-[var(--color-border)]">{String(params.context_window)} ctx</span>
                )}
              </div>

              <div className="flex gap-2 text-xs">
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
