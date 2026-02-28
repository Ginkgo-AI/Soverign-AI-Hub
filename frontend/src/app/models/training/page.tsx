"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  listModels,
  listDatasets,
  startTraining,
  listTrainingJobs,
  getTrainingStatus,
  getTrainingMetrics,
  cancelTraining,
  type Model,
  type Dataset,
  type TrainingJob,
  type TrainingMetrics,
  type TrainingConfig,
} from "@/lib/models";

// ---------------------------------------------------------------------------
// SVG Loss Curve Chart
// ---------------------------------------------------------------------------

function LossCurveChart({
  data,
}: {
  data: Array<{ step: number; loss: number }>;
}) {
  if (!data || data.length < 2) {
    return (
      <div className="h-40 flex items-center justify-center text-sm text-[var(--color-text-muted)]">
        Not enough data for chart
      </div>
    );
  }

  const width = 500;
  const height = 160;
  const pad = { top: 10, right: 10, bottom: 25, left: 45 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const maxStep = Math.max(...data.map((d) => d.step));
  const minLoss = Math.min(...data.map((d) => d.loss));
  const maxLoss = Math.max(...data.map((d) => d.loss));
  const lossRange = maxLoss - minLoss || 1;

  const points = data
    .map((d) => {
      const x = pad.left + (d.step / maxStep) * plotW;
      const y = pad.top + (1 - (d.loss - minLoss) / lossRange) * plotH;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const y = pad.top + f * plotH;
        const val = maxLoss - f * lossRange;
        return (
          <g key={f}>
            <line
              x1={pad.left}
              y1={y}
              x2={width - pad.right}
              y2={y}
              stroke="var(--color-border)"
              strokeWidth="0.5"
            />
            <text
              x={pad.left - 5}
              y={y + 3}
              textAnchor="end"
              fill="var(--color-text-muted)"
              fontSize="8"
            >
              {val.toFixed(2)}
            </text>
          </g>
        );
      })}
      {/* X axis label */}
      <text
        x={width / 2}
        y={height - 2}
        textAnchor="middle"
        fill="var(--color-text-muted)"
        fontSize="8"
      >
        Training Steps
      </text>
      {/* Loss line */}
      <polyline
        points={points}
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Training Presets
// ---------------------------------------------------------------------------

const PRESETS: Record<string, Partial<TrainingConfig>> = {
  quick: {
    epochs: 1,
    learning_rate: 3e-4,
    batch_size: 8,
    lora_rank: 8,
    lora_alpha: 16,
    preset: "quick",
  },
  standard: {
    epochs: 3,
    learning_rate: 2e-4,
    batch_size: 4,
    lora_rank: 16,
    lora_alpha: 32,
    preset: "standard",
  },
  thorough: {
    epochs: 5,
    learning_rate: 1e-4,
    batch_size: 2,
    lora_rank: 32,
    lora_alpha: 64,
    preset: "thorough",
  },
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  running: "bg-blue-500/20 text-blue-400",
  completed: "bg-[var(--color-success)]/20 text-[var(--color-success)]",
  failed: "bg-[var(--color-danger)]/20 text-[var(--color-danger)]",
  cancelled: "bg-gray-500/20 text-gray-400",
};

export default function TrainingPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [metricsMap, setMetricsMap] = useState<Record<string, TrainingMetrics>>({});
  const [loading, setLoading] = useState(true);

  // Form state
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [activePreset, setActivePreset] = useState("standard");
  const [learningRate, setLearningRate] = useState(2e-4);
  const [epochs, setEpochs] = useState(3);
  const [batchSize, setBatchSize] = useState(4);
  const [loraRank, setLoraRank] = useState(16);
  const [loraAlpha, setLoraAlpha] = useState(32);
  const [quantization, setQuantization] = useState<"4bit" | "8bit" | "none">("4bit");
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [modelsRes, datasetsRes, jobsRes] = await Promise.all([
        listModels(),
        listDatasets(),
        listTrainingJobs(),
      ]);
      setModels(modelsRes.models);
      setDatasets(datasetsRes.datasets);
      setJobs(jobsRes.jobs);
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll running jobs
  useEffect(() => {
    const runningJobs = jobs.filter((j) => j.status === "running" || j.status === "pending");
    if (runningJobs.length === 0) return;

    const interval = setInterval(async () => {
      for (const job of runningJobs) {
        try {
          const updated = await getTrainingStatus(job.id);
          setJobs((prev) => prev.map((j) => (j.id === job.id ? updated : j)));
          if (updated.status === "running") {
            const metrics = await getTrainingMetrics(job.id);
            setMetricsMap((prev) => ({ ...prev, [job.id]: metrics }));
          }
        } catch {
          // ignore polling errors
        }
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [jobs]);

  const applyPreset = (name: string) => {
    const p = PRESETS[name];
    if (!p) return;
    setActivePreset(name);
    if (p.learning_rate !== undefined) setLearningRate(p.learning_rate);
    if (p.epochs !== undefined) setEpochs(p.epochs);
    if (p.batch_size !== undefined) setBatchSize(p.batch_size);
    if (p.lora_rank !== undefined) setLoraRank(p.lora_rank);
    if (p.lora_alpha !== undefined) setLoraAlpha(p.lora_alpha);
  };

  const handleStartTraining = async () => {
    if (!selectedModel || !selectedDataset) {
      alert("Please select a base model and dataset.");
      return;
    }
    setSubmitting(true);
    try {
      const config: TrainingConfig = {
        base_model: selectedModel,
        dataset_id: selectedDataset,
        learning_rate: learningRate,
        epochs,
        batch_size: batchSize,
        lora_rank: loraRank,
        lora_alpha: loraAlpha,
        quantization,
        preset: activePreset as "quick" | "standard" | "thorough",
      };
      await startTraining(config);
      await fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start training";
      alert(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await cancelTraining(jobId);
      await fetchData();
    } catch {
      alert("Failed to cancel training job");
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-[var(--color-text-muted)]">Loading...</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link href="/models" className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            Models
          </Link>
          <h2 className="text-2xl font-semibold">Fine-Tuning</h2>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Training launcher form */}
        <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">New Training Job</h3>

          <div className="space-y-4">
            {/* Base model */}
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Base Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="">Select a model...</option>
                {models.map((m) => (
                  <option key={m.id} value={m.name}>
                    {m.name} ({m.backend})
                  </option>
                ))}
              </select>
            </div>

            {/* Dataset */}
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Dataset</label>
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="">Select a dataset...</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.sample_count} samples)
                  </option>
                ))}
              </select>
              <Link href="/models/datasets" className="text-xs text-[var(--color-primary)] mt-1 inline-block">
                Upload a new dataset
              </Link>
            </div>

            {/* Presets */}
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Preset</label>
              <div className="flex gap-2">
                {(["quick", "standard", "thorough"] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => applyPreset(p)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                      activePreset === p
                        ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                        : "border-[var(--color-border)] hover:bg-[var(--color-surface)]"
                    }`}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Configuration */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Learning Rate</label>
                <input
                  type="number"
                  value={learningRate}
                  onChange={(e) => setLearningRate(parseFloat(e.target.value))}
                  step="0.0001"
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Epochs</label>
                <input
                  type="number"
                  value={epochs}
                  onChange={(e) => setEpochs(parseInt(e.target.value))}
                  min={1}
                  max={100}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Batch Size</label>
                <input
                  type="number"
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value))}
                  min={1}
                  max={256}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">LoRA Rank</label>
                <input
                  type="number"
                  value={loraRank}
                  onChange={(e) => setLoraRank(parseInt(e.target.value))}
                  min={1}
                  max={256}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">LoRA Alpha</label>
                <input
                  type="number"
                  value={loraAlpha}
                  onChange={(e) => setLoraAlpha(parseInt(e.target.value))}
                  min={1}
                  max={512}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-[var(--color-text-muted)] mb-1">Quantization</label>
                <select
                  value={quantization}
                  onChange={(e) => setQuantization(e.target.value as "4bit" | "8bit" | "none")}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                >
                  <option value="4bit">4-bit (QLoRA)</option>
                  <option value="8bit">8-bit</option>
                  <option value="none">None (Full)</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleStartTraining}
              disabled={submitting || !selectedModel || !selectedDataset}
              className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white font-medium text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? "Starting..." : "Start Training"}
            </button>
          </div>
        </div>

        {/* Active / Recent Jobs */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium">Training Jobs</h3>

          {jobs.length === 0 && (
            <p className="text-sm text-[var(--color-text-muted)]">No training jobs yet.</p>
          )}

          {jobs.map((job) => {
            const metrics = metricsMap[job.id];
            return (
              <div
                key={job.id}
                className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-sm">{job.base_model}</p>
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {new Date(job.created_at).toLocaleString()}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 text-xs rounded ${STATUS_COLORS[job.status] || ""}`}>
                    {job.status}
                  </span>
                </div>

                {/* Progress bar */}
                {(job.status === "running" || job.status === "pending") && (
                  <div className="mb-2">
                    <div className="flex justify-between text-xs text-[var(--color-text-muted)] mb-1">
                      <span>Progress</span>
                      <span>{Math.round(job.progress * 100)}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-500"
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Loss curve */}
                {metrics && metrics.loss_history.length > 1 && (
                  <div className="mt-2 border-t border-[var(--color-border)] pt-2">
                    <p className="text-xs text-[var(--color-text-muted)] mb-1">Loss Curve</p>
                    <LossCurveChart data={metrics.loss_history} />
                  </div>
                )}

                {/* Error message */}
                {job.error_message && (
                  <p className="text-xs text-[var(--color-danger)] mt-2">{job.error_message}</p>
                )}

                {/* Actions */}
                <div className="flex gap-2 mt-2">
                  {(job.status === "running" || job.status === "pending") && (
                    <button
                      onClick={() => handleCancel(job.id)}
                      className="px-3 py-1 text-xs rounded text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                    >
                      Cancel
                    </button>
                  )}
                  {job.status === "completed" && job.output_path && (
                    <span className="px-3 py-1 text-xs rounded bg-[var(--color-success)]/10 text-[var(--color-success)]">
                      Adapter saved
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
