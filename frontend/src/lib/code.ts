/**
 * Code Assistant API helpers -- Phase 5.
 */

import { apiJson, apiFetch } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Workspace {
  id: string;
  name: string;
  description: string;
  path: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  file_tree?: FileTreeNode[];
}

export interface FileTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  language: string | null;
  line_count: number | null;
  children: FileTreeNode[] | null;
}

export interface FileContent {
  path: string;
  content: string;
  language: string | null;
  size: number;
  line_count: number;
}

export interface ExecuteResult {
  execution_id: string | null;
  session_id: string | null;
  stdout: string;
  stderr: string;
  return_value: string | null;
  exit_code: number;
  execution_time_ms: number;
  language: string;
}

export interface AnalysisIssue {
  line: number | null;
  column: number | null;
  severity: string;
  message: string;
  rule: string | null;
}

export interface AnalyzeResult {
  issues: AnalysisIssue[];
  summary: string;
  issue_count: number;
  language: string;
}

export interface CodeGenResult {
  code: string;
  explanation: string;
  language: string;
}

export interface ExplainResult {
  explanation: string;
  language: string;
}

export interface ReviewFinding {
  line: number | null;
  severity: string;
  category: string;
  message: string;
  suggestion: string | null;
}

export interface ReviewResult {
  findings: ReviewFinding[];
  summary: string;
  overall_quality: string;
}

export interface DiffSummary {
  summary: string;
  files_changed: number;
  additions: number;
  deletions: number;
  file_summaries: { file: string; changes: string }[];
}

export interface CommitMessage {
  message: string;
  subject: string;
  body: string;
}

// ---------------------------------------------------------------------------
// Workspace API
// ---------------------------------------------------------------------------

export async function createWorkspace(
  name: string,
  description: string = ""
): Promise<Workspace> {
  return apiJson<Workspace>("/api/code/workspaces", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function listWorkspaces(): Promise<{
  workspaces: Workspace[];
  total: number;
}> {
  return apiJson("/api/code/workspaces");
}

export async function getWorkspace(wsId: string): Promise<Workspace> {
  return apiJson<Workspace>(`/api/code/workspaces/${wsId}`);
}

export async function deleteWorkspace(wsId: string): Promise<void> {
  await apiFetch(`/api/code/workspaces/${wsId}`, { method: "DELETE" });
}

export async function readFile(
  wsId: string,
  path: string
): Promise<FileContent> {
  return apiJson<FileContent>(
    `/api/code/workspaces/${wsId}/files/${path}`
  );
}

export async function writeFile(
  wsId: string,
  path: string,
  content: string
): Promise<FileContent> {
  return apiJson<FileContent>(
    `/api/code/workspaces/${wsId}/files/${path}`,
    {
      method: "PUT",
      body: JSON.stringify({ content }),
    }
  );
}

export async function deleteFile(
  wsId: string,
  path: string
): Promise<void> {
  await apiFetch(`/api/code/workspaces/${wsId}/files/${path}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// Code execution API
// ---------------------------------------------------------------------------

export async function executeCode(
  code: string,
  language: string = "python",
  sessionId?: string,
  timeout: number = 30
): Promise<ExecuteResult> {
  return apiJson<ExecuteResult>("/api/code/execute", {
    method: "POST",
    body: JSON.stringify({
      code,
      language,
      session_id: sessionId || null,
      timeout,
    }),
  });
}

// ---------------------------------------------------------------------------
// Code analysis API
// ---------------------------------------------------------------------------

export async function analyzeCode(
  code: string,
  language: string = "python",
  analysisType: string = "full"
): Promise<AnalyzeResult> {
  return apiJson<AnalyzeResult>("/api/code/analyze", {
    method: "POST",
    body: JSON.stringify({ code, language, analysis_type: analysisType }),
  });
}

export async function explainCode(
  code: string,
  language: string = "python",
  detailLevel: string = "normal"
): Promise<ExplainResult> {
  return apiJson<ExplainResult>("/api/code/explain", {
    method: "POST",
    body: JSON.stringify({ code, language, detail_level: detailLevel }),
  });
}

export async function generateCode(
  prompt: string,
  language: string = "python",
  context?: string
): Promise<CodeGenResult> {
  return apiJson<CodeGenResult>("/api/code/generate", {
    method: "POST",
    body: JSON.stringify({ prompt, language, context: context || null }),
  });
}

export async function reviewCode(
  code?: string,
  diff?: string,
  language: string = "python",
  focus: string = "general"
): Promise<ReviewResult> {
  return apiJson<ReviewResult>("/api/code/review", {
    method: "POST",
    body: JSON.stringify({
      code: code || null,
      diff: diff || null,
      language,
      focus,
    }),
  });
}

// ---------------------------------------------------------------------------
// Git API
// ---------------------------------------------------------------------------

export async function getDiffSummary(diff: string): Promise<DiffSummary> {
  return apiJson<DiffSummary>("/api/code/git/diff-summary", {
    method: "POST",
    body: JSON.stringify({ diff }),
  });
}

export async function getCommitMessage(
  diff: string,
  style: string = "conventional"
): Promise<CommitMessage> {
  return apiJson<CommitMessage>("/api/code/git/commit-message", {
    method: "POST",
    body: JSON.stringify({ diff, style }),
  });
}
