/**
 * Phase 7 — Model Management, Training, Datasets, and Evaluation API helpers.
 * Full TypeScript types and API functions for all model management endpoints.
 */

import { apiFetch, apiJson } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Model {
  id: string;
  name: string;
  version: string;
  backend: "vllm" | "llama-cpp";
  file_path: string;
  quantization: string | null;
  parameters: Record<string, unknown> | null;
  status: "downloading" | "available" | "loaded" | "error";
  created_at: string;
  updated_at: string;
}

export interface ModelListResponse {
  models: Model[];
  total: number;
}

export interface ModelRegisterRequest {
  name: string;
  version?: string;
  backend: "vllm" | "llama-cpp";
  file_path: string;
  quantization?: string;
  parameters?: Record<string, unknown>;
}

export interface ModelScanResult {
  discovered: number;
  registered: number;
  models: Model[];
}

export interface ModelDownloadRequest {
  source: string;
  filename?: string;
  destination?: string;
}

export interface TrainingConfig {
  base_model: string;
  dataset_id?: string;
  dataset_path?: string;
  output_dir?: string;
  learning_rate?: number;
  epochs?: number;
  batch_size?: number;
  lora_rank?: number;
  lora_alpha?: number;
  target_modules?: string[];
  quantization?: "4bit" | "8bit" | "none";
  max_seq_length?: number;
  warmup_steps?: number;
  gradient_accumulation_steps?: number;
  preset?: "quick" | "standard" | "thorough";
}

export interface TrainingJob {
  id: string;
  user_id: string;
  base_model: string;
  dataset_path: string;
  config: Record<string, unknown> | null;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  metrics: Record<string, unknown> | null;
  output_path: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TrainingJobListResponse {
  jobs: TrainingJob[];
  total: number;
}

export interface TrainingMetrics {
  job_id: string;
  loss_history: Array<{ step: number; loss: number; learning_rate?: number }>;
  eval_history: Array<Record<string, unknown>>;
  final_metrics: Record<string, unknown> | null;
}

export interface AdapterInfo {
  job_id: string;
  base_model: string;
  path: string;
  created_at: string | null;
}

export interface AdapterListResponse {
  adapters: AdapterInfo[];
  total: number;
}

export interface Dataset {
  id: string;
  user_id: string;
  name: string;
  format: string;
  file_path: string;
  sample_count: number;
  token_stats: Record<string, unknown> | null;
  created_at: string;
}

export interface DatasetListResponse {
  datasets: Dataset[];
  total: number;
}

export interface DatasetStats {
  sample_count: number;
  avg_token_length: number;
  min_token_length: number;
  max_token_length: number;
  token_distribution: Record<string, number> | null;
  format_detected: string;
  schema_fields: string[];
}

export interface DatasetPreview {
  samples: Record<string, unknown>[];
  total: number;
}

export interface BenchmarkRequest {
  model_name: string;
  benchmark: string;
}

export interface BenchmarkResult {
  id: string;
  model_name: string;
  benchmark: string;
  score: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface BenchmarkResultListResponse {
  results: BenchmarkResult[];
  total: number;
}

export interface BenchmarkComparison {
  model_a: string;
  model_b: string;
  benchmark: string;
  score_a: number;
  score_b: number;
  details_a: Record<string, unknown> | null;
  details_b: Record<string, unknown> | null;
  winner: string;
}

export interface ABTest {
  id: string;
  model_a: string;
  model_b: string;
  traffic_split: number;
  status: string;
  metrics: Record<string, unknown> | null;
  created_at: string;
  created_by: string;
}

export interface ABTestResult {
  id: string;
  model_a: string;
  model_b: string;
  total_requests: number;
  model_a_requests: number;
  model_b_requests: number;
  model_a_preferred: number;
  model_b_preferred: number;
  model_a_avg_rating: number | null;
  model_b_avg_rating: number | null;
  winner: string | null;
  status: string;
}

// ---------------------------------------------------------------------------
// Model Registry API
// ---------------------------------------------------------------------------

export async function listModels(params?: {
  backend?: string;
  status?: string;
  quantization?: string;
}): Promise<ModelListResponse> {
  const query = new URLSearchParams();
  if (params?.backend) query.set("backend", params.backend);
  if (params?.status) query.set("status", params.status);
  if (params?.quantization) query.set("quantization", params.quantization);
  const qs = query.toString();
  return apiJson<ModelListResponse>(`/api/models${qs ? `?${qs}` : ""}`);
}

export async function getModel(modelId: string): Promise<Model> {
  return apiJson<Model>(`/api/models/${modelId}`);
}

export async function registerModel(data: ModelRegisterRequest): Promise<Model> {
  return apiJson<Model>("/api/models", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateModel(
  modelId: string,
  data: Partial<ModelRegisterRequest & { status: string }>
): Promise<Model> {
  return apiJson<Model>(`/api/models/${modelId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteModel(
  modelId: string,
  deleteFiles = false
): Promise<void> {
  await apiFetch(`/api/models/${modelId}?delete_files=${deleteFiles}`, {
    method: "DELETE",
  });
}

export async function scanModels(path = "/models"): Promise<ModelScanResult> {
  return apiJson<ModelScanResult>("/api/models/scan", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export async function downloadModel(
  data: ModelDownloadRequest
): Promise<{ model_id: string; status: string; message: string }> {
  return apiJson("/api/models/download", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Training API
// ---------------------------------------------------------------------------

export async function startTraining(
  config: TrainingConfig
): Promise<TrainingJob> {
  return apiJson<TrainingJob>("/api/training/jobs", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function listTrainingJobs(
  status?: string
): Promise<TrainingJobListResponse> {
  const qs = status ? `?status=${status}` : "";
  return apiJson<TrainingJobListResponse>(`/api/training/jobs${qs}`);
}

export async function getTrainingStatus(
  jobId: string
): Promise<TrainingJob> {
  return apiJson<TrainingJob>(`/api/training/jobs/${jobId}`);
}

export async function cancelTraining(jobId: string): Promise<TrainingJob> {
  return apiJson<TrainingJob>(`/api/training/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export async function getTrainingMetrics(
  jobId: string
): Promise<TrainingMetrics> {
  return apiJson<TrainingMetrics>(`/api/training/jobs/${jobId}/metrics`);
}

export async function listAdapters(): Promise<AdapterListResponse> {
  return apiJson<AdapterListResponse>("/api/training/adapters");
}

export async function deleteAdapter(jobId: string): Promise<void> {
  await apiFetch(`/api/training/adapters/${jobId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Dataset API
// ---------------------------------------------------------------------------

export async function uploadDataset(
  file: File,
  name: string,
  format = "jsonl"
): Promise<Dataset> {
  const formData = new FormData();
  formData.append("file", file);
  const url = `/api/training/datasets?name=${encodeURIComponent(name)}&format=${format}`;
  const response = await apiFetch(url, {
    method: "POST",
    body: formData,
    headers: {}, // Let browser set content-type with boundary
  });
  return response.json();
}

export async function listDatasets(): Promise<DatasetListResponse> {
  return apiJson<DatasetListResponse>("/api/training/datasets");
}

export async function getDataset(dsId: string): Promise<Dataset> {
  return apiJson<Dataset>(`/api/training/datasets/${dsId}`);
}

export async function getDatasetStats(dsId: string): Promise<DatasetStats> {
  return apiJson<DatasetStats>(`/api/training/datasets/${dsId}/stats`);
}

export async function previewDataset(
  dsId: string,
  limit = 10
): Promise<DatasetPreview> {
  return apiJson<DatasetPreview>(
    `/api/training/datasets/${dsId}/preview?limit=${limit}`
  );
}

export async function createDatasetFromConversations(
  conversationIds: string[],
  name: string,
  format = "messages"
): Promise<Dataset> {
  return apiJson<Dataset>("/api/training/datasets/from-conversations", {
    method: "POST",
    body: JSON.stringify({
      conversation_ids: conversationIds,
      name,
      format,
    }),
  });
}

export async function deleteDataset(dsId: string): Promise<void> {
  await apiFetch(`/api/training/datasets/${dsId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Evaluation API
// ---------------------------------------------------------------------------

export async function runBenchmark(
  data: BenchmarkRequest
): Promise<BenchmarkResult> {
  return apiJson<BenchmarkResult>("/api/evaluation/benchmark", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listBenchmarkResults(params?: {
  model_name?: string;
  benchmark?: string;
}): Promise<BenchmarkResultListResponse> {
  const query = new URLSearchParams();
  if (params?.model_name) query.set("model_name", params.model_name);
  if (params?.benchmark) query.set("benchmark", params.benchmark);
  const qs = query.toString();
  return apiJson<BenchmarkResultListResponse>(
    `/api/evaluation/results${qs ? `?${qs}` : ""}`
  );
}

export async function compareModels(
  modelA: string,
  modelB: string,
  benchmark: string
): Promise<BenchmarkComparison> {
  return apiJson<BenchmarkComparison>("/api/evaluation/compare", {
    method: "POST",
    body: JSON.stringify({ model_a: modelA, model_b: modelB, benchmark }),
  });
}

export async function createABTest(
  modelA: string,
  modelB: string,
  trafficSplit = 0.5
): Promise<ABTest> {
  return apiJson<ABTest>("/api/evaluation/ab-test", {
    method: "POST",
    body: JSON.stringify({
      model_a: modelA,
      model_b: modelB,
      traffic_split: trafficSplit,
    }),
  });
}

export async function getABTestResults(
  testId: string
): Promise<ABTestResult> {
  return apiJson<ABTestResult>(`/api/evaluation/ab-test/${testId}`);
}
