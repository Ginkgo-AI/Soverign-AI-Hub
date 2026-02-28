"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  listDatasets,
  uploadDataset,
  deleteDataset,
  getDatasetStats,
  previewDataset,
  type Dataset,
  type DatasetStats,
  type DatasetPreview,
} from "@/lib/models";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [uploadFormat, setUploadFormat] = useState("jsonl");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Preview/stats state
  const [selectedDs, setSelectedDs] = useState<Dataset | null>(null);
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const fetchDatasets = async () => {
    try {
      const res = await listDatasets();
      setDatasets(res.datasets);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !uploadName) {
      alert("Please provide a name and select a file.");
      return;
    }
    setUploading(true);
    try {
      await uploadDataset(file, uploadName, uploadFormat);
      setUploadName("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await fetchDatasets();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      alert(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this dataset?")) return;
    try {
      await deleteDataset(id);
      if (selectedDs?.id === id) {
        setSelectedDs(null);
        setStats(null);
        setPreview(null);
      }
      await fetchDatasets();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Delete failed";
      alert(msg);
    }
  };

  const handleViewDetails = async (ds: Dataset) => {
    setSelectedDs(ds);
    setLoadingDetails(true);
    try {
      const [statsRes, previewRes] = await Promise.all([
        getDatasetStats(ds.id),
        previewDataset(ds.id, 10),
      ]);
      setStats(statsRes);
      setPreview(previewRes);
    } catch {
      // silent
    } finally {
      setLoadingDetails(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link href="/models" className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            Models
          </Link>
          <h2 className="text-2xl font-semibold">Datasets</h2>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Upload section */}
        <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">Upload Dataset</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Dataset Name</label>
              <input
                type="text"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="My training data"
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Format</label>
              <select
                value={uploadFormat}
                onChange={(e) => setUploadFormat(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="jsonl">JSONL</option>
                <option value="csv">CSV</option>
                <option value="alpaca">Alpaca</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">File</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".jsonl,.csv,.json"
                className="w-full text-sm"
              />
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading || !uploadName}
              className="w-full py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>

            <div className="pt-2 border-t border-[var(--color-border)]">
              <Link
                href="/models/datasets"
                className="text-xs text-[var(--color-text-muted)]"
              >
                Supported: JSONL (instruction or messages format), CSV
              </Link>
            </div>
          </div>
        </div>

        {/* Dataset list */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-lg font-medium">Your Datasets</h3>

          {loading && <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>}

          {!loading && datasets.length === 0 && (
            <p className="text-sm text-[var(--color-text-muted)]">
              No datasets yet. Upload a JSONL or CSV file to get started.
            </p>
          )}

          <div className="space-y-2">
            {datasets.map((ds) => {
              const tokenStats = ds.token_stats || {};
              return (
                <div
                  key={ds.id}
                  className={`p-4 rounded-xl border bg-[var(--color-surface)] transition-colors cursor-pointer ${
                    selectedDs?.id === ds.id
                      ? "border-[var(--color-primary)]"
                      : "border-[var(--color-border)] hover:border-[var(--color-primary)]/50"
                  }`}
                  onClick={() => handleViewDetails(ds)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-sm">{ds.name}</h4>
                      <div className="flex gap-3 mt-1 text-xs text-[var(--color-text-muted)]">
                        <span>{ds.sample_count} samples</span>
                        <span>{ds.format}</span>
                        {tokenStats.avg_token_length && (
                          <span>~{Math.round(Number(tokenStats.avg_token_length))} avg tokens</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 items-center">
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {new Date(ds.created_at).toLocaleDateString()}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(ds.id);
                        }}
                        className="px-2 py-1 text-xs text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 rounded"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Detail panel */}
          {selectedDs && (
            <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
              <h4 className="font-medium mb-3">{selectedDs.name} - Details</h4>

              {loadingDetails ? (
                <p className="text-sm text-[var(--color-text-muted)]">Loading details...</p>
              ) : (
                <div className="space-y-4">
                  {/* Stats */}
                  {stats && (
                    <div>
                      <p className="text-sm text-[var(--color-text-muted)] mb-2">Statistics</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                        <div className="p-2 rounded bg-[var(--color-bg)]">
                          <span className="block text-xs text-[var(--color-text-muted)]">Samples</span>
                          <span className="font-medium">{stats.sample_count}</span>
                        </div>
                        <div className="p-2 rounded bg-[var(--color-bg)]">
                          <span className="block text-xs text-[var(--color-text-muted)]">Avg Tokens</span>
                          <span className="font-medium">{Math.round(stats.avg_token_length)}</span>
                        </div>
                        <div className="p-2 rounded bg-[var(--color-bg)]">
                          <span className="block text-xs text-[var(--color-text-muted)]">Min Tokens</span>
                          <span className="font-medium">{stats.min_token_length}</span>
                        </div>
                        <div className="p-2 rounded bg-[var(--color-bg)]">
                          <span className="block text-xs text-[var(--color-text-muted)]">Max Tokens</span>
                          <span className="font-medium">{stats.max_token_length}</span>
                        </div>
                      </div>
                      {stats.token_distribution && (
                        <div className="mt-2">
                          <p className="text-xs text-[var(--color-text-muted)] mb-1">Token Length Distribution</p>
                          <div className="flex gap-1 items-end h-16">
                            {Object.entries(stats.token_distribution).map(([bucket, count]) => {
                              const maxCount = Math.max(...Object.values(stats.token_distribution || {}));
                              const height = maxCount > 0 ? (count / maxCount) * 100 : 0;
                              return (
                                <div key={bucket} className="flex-1 flex flex-col items-center">
                                  <div
                                    className="w-full rounded-t bg-[var(--color-primary)]/60"
                                    style={{ height: `${height}%`, minHeight: count > 0 ? "2px" : "0" }}
                                  />
                                  <span className="text-[8px] text-[var(--color-text-muted)] mt-1 truncate w-full text-center">
                                    {bucket}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      <div className="mt-2 text-xs text-[var(--color-text-muted)]">
                        Format: {stats.format_detected} | Fields: {stats.schema_fields.join(", ")}
                      </div>
                    </div>
                  )}

                  {/* Preview */}
                  {preview && preview.samples.length > 0 && (
                    <div>
                      <p className="text-sm text-[var(--color-text-muted)] mb-2">
                        Preview (first {preview.samples.length} of {preview.total} samples)
                      </p>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {preview.samples.map((sample, i) => (
                          <div
                            key={i}
                            className="p-2 rounded bg-[var(--color-bg)] text-xs font-mono overflow-x-auto"
                          >
                            <pre className="whitespace-pre-wrap break-words">
                              {JSON.stringify(sample, null, 2)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
