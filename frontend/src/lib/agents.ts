/**
 * Agents API helpers
 */

import { apiFetch, apiJson } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Agent {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  model: string;
  created_at: string;
  updated_at: string;
}

export interface AgentListResponse {
  agents: Agent[];
  total: number;
}

export interface Tool {
  name: string;
  description: string;
  category: string;
  parameters: Record<string, unknown>;
}

export interface ToolListResponse {
  tools: Tool[];
}

export interface ExecutionStep {
  step_number: number;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  reasoning: string | null;
  duration_ms: number | null;
  status: string;
}

export interface Execution {
  id: string;
  agent_id: string;
  prompt: string;
  status: "running" | "completed" | "failed" | "awaiting_approval";
  steps: ExecutionStep[];
  result: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Agents API
// ---------------------------------------------------------------------------

export async function fetchAgents(): Promise<AgentListResponse> {
  return apiJson<AgentListResponse>("/api/agents");
}

export async function createAgent(data: {
  name: string;
  description?: string;
  system_prompt?: string;
  tools?: string[];
  model?: string;
}): Promise<Agent> {
  return apiJson<Agent>("/api/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getAgent(agentId: string): Promise<Agent> {
  return apiJson<Agent>(`/api/agents/${agentId}`);
}

export async function deleteAgent(agentId: string): Promise<void> {
  await apiFetch(`/api/agents/${agentId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Tools API
// ---------------------------------------------------------------------------

export async function fetchTools(): Promise<ToolListResponse> {
  return apiJson<ToolListResponse>("/api/agents/tools");
}

// ---------------------------------------------------------------------------
// Execution API
// ---------------------------------------------------------------------------

export async function executeAgent(
  agentId: string,
  prompt: string
): Promise<Execution> {
  return apiJson<Execution>(`/api/agents/${agentId}/execute`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function getExecution(
  agentId: string,
  executionId: string
): Promise<Execution> {
  return apiJson<Execution>(
    `/api/agents/${agentId}/executions/${executionId}`
  );
}
