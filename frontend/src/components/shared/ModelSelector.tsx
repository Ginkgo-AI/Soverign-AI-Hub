"use client";

import { useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface ModelInfo {
  id: string;
  _backend?: string;
}

interface ModelSelectorProps {
  selectedModel: string;
  selectedBackend: string;
  onModelChange: (model: string, backend: string) => void;
}

export function ModelSelector({
  selectedModel,
  selectedBackend,
  onModelChange,
}: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);

  useEffect(() => {
    apiJson<{ data: ModelInfo[] }>("/v1/models")
      .then((res) => setModels(res.data || []))
      .catch(() => {});
  }, []);

  return (
    <div className="flex items-center gap-2">
      <select
        value={selectedModel || ""}
        onChange={(e) => {
          const model = models.find((m) => m.id === e.target.value);
          onModelChange(e.target.value, model?._backend || selectedBackend);
        }}
        className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-[var(--color-accent)]"
      >
        <option value="">Auto (default model)</option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id} ({m._backend})
          </option>
        ))}
      </select>
    </div>
  );
}
