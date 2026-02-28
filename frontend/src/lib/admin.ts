/**
 * Admin API helpers — Phase 6: Security, Compliance & Governance
 */

import { apiFetch, apiJson } from "./api";

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------
export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UsersResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchUsers(
  page = 1,
  pageSize = 50,
  search?: string
): Promise<UsersResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (search) params.set("search", search);
  return apiJson<UsersResponse>(`/api/admin/users?${params}`);
}

export async function updateUserRole(
  userId: string,
  role: string
): Promise<User> {
  return apiJson<User>(`/api/admin/users/${userId}/role`, {
    method: "PUT",
    body: JSON.stringify({ role }),
  });
}

export async function updateUserActive(
  userId: string,
  isActive: boolean
): Promise<User> {
  return apiJson<User>(`/api/admin/users/${userId}/active`, {
    method: "PUT",
    body: JSON.stringify({ is_active: isActive }),
  });
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------
export interface AuditEntry {
  id: number;
  timestamp: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  request_summary: string | null;
  response_summary: string | null;
  ip_address: string | null;
  classification_level: string;
}

export interface AuditResponse {
  entries: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AuditFilters {
  page?: number;
  page_size?: number;
  user_id?: string;
  action?: string;
  resource_type?: string;
  classification_level?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export async function fetchAuditLogs(
  filters: AuditFilters = {}
): Promise<AuditResponse> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  return apiJson<AuditResponse>(`/api/admin/audit?${params}`);
}

export async function exportAuditLogs(
  format: "json" | "csv" | "syslog" = "json",
  dateFrom?: string,
  dateTo?: string
): Promise<string> {
  const params = new URLSearchParams({ format });
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const resp = await apiFetch(`/api/admin/audit/export?${params}`);
  return resp.text();
}

export interface AuditStats {
  total_events: number;
  events_today: number;
  events_this_week: number;
  top_actions: { action: string; count: number }[];
  top_users: { user_id: string; count: number }[];
  events_by_day: { date: string; count: number }[];
  events_by_classification: { classification: string; count: number }[];
}

export async function getAuditStats(
  dateFrom?: string,
  dateTo?: string
): Promise<AuditStats> {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return apiJson<AuditStats>(`/api/admin/audit/stats?${params}`);
}

// ---------------------------------------------------------------------------
// Security config
// ---------------------------------------------------------------------------
export interface SecurityConfig {
  airgap_mode: boolean;
  classification_levels: string[];
  session_timeout_minutes: number;
  max_concurrent_sessions: number;
  encryption_enabled: boolean;
  audit_retention_days: number;
  siem_endpoint: string;
  keycloak_enabled: boolean;
}

export async function getSecurityConfig(): Promise<SecurityConfig> {
  return apiJson<SecurityConfig>("/api/admin/security/config");
}

export async function updateSecurityConfig(
  updates: Partial<SecurityConfig>
): Promise<SecurityConfig> {
  return apiJson<SecurityConfig>("/api/admin/security/config", {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------
export interface ComplianceControl {
  control_id: string;
  control_name: string;
  control_family: string;
  status: "implemented" | "partial" | "planned" | "not_applicable";
  evidence: string;
  notes: string;
}

export interface ComplianceReport {
  generated_at: string;
  framework: string;
  overall_score: number;
  total_controls: number;
  implemented: number;
  partial: number;
  planned: number;
  controls: ComplianceControl[];
}

export async function getComplianceReport(): Promise<ComplianceReport> {
  return apiJson<ComplianceReport>("/api/admin/compliance/report");
}

// ---------------------------------------------------------------------------
// System health
// ---------------------------------------------------------------------------
export interface SystemHealth {
  status: string;
  checks: Record<string, string>;
  timestamp: string;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  return apiJson<SystemHealth>("/api/admin/system/health");
}
