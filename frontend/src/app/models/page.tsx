"use client";

import { useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface ModelInfo {
  id: string;
  object: string;
  _backend?: string;
}

export default function ModelsPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiJson<{ data: ModelInfo[] }>("/v1/models")
      .then((res) => {
        setModels(res.data || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold mb-4">Models</h2>

      {loading && <p className="text-[var(--color-text-muted)]">Loading models...</p>}
      {error && <p className="text-[var(--color-danger)]">Error: {error}</p>}

      {!loading && !error && models.length === 0 && (
        <p className="text-[var(--color-text-muted)]">
          No models loaded. Start a vLLM or llama.cpp backend to see available models.
        </p>
      )}

      <div className="grid gap-3 mt-4">
        {models.map((model) => (
          <div
            key={model.id}
            className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium">{model.id}</h3>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  Backend: {model._backend || "unknown"}
                </p>
              </div>
              <span className="px-2 py-1 text-xs rounded bg-[var(--color-success)]/20 text-[var(--color-success)]">
                loaded
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
