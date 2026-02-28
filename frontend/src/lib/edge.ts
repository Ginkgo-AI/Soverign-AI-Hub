/**
 * Edge Device API helpers — Phase 8: Edge Deployment
 */

import { apiFetch, apiJson } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EdgeDevice {
  id: string;
  name: string;
  agent_id: string;
  status: "active" | "inactive" | "revoked";
  last_seen: string | null;
  sync_state: Record<string, SyncStateEntry> | null;
  config_version: string;
  classification_level: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface EdgeDeviceWithKey extends EdgeDevice {
  api_key: string;
}

export interface EdgeDeviceListResponse {
  devices: EdgeDevice[];
  total: number;
}

export interface SyncStateEntry {
  last_sync: string;
  items: number;
  status: string;
}

// ---------------------------------------------------------------------------
// Device management
// ---------------------------------------------------------------------------

export async function registerDevice(
  name: string,
  options?: {
    agent_id?: string;
    classification_level?: string;
    metadata?: Record<string, unknown>;
  }
): Promise<EdgeDeviceWithKey> {
  return apiJson<EdgeDeviceWithKey>("/api/edge/devices", {
    method: "POST",
    body: JSON.stringify({
      name,
      agent_id: options?.agent_id,
      classification_level: options?.classification_level || "UNCLASSIFIED",
      metadata: options?.metadata,
    }),
  });
}

export async function listDevices(
  status?: string
): Promise<EdgeDeviceListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const query = params.toString() ? `?${params}` : "";
  return apiJson<EdgeDeviceListResponse>(`/api/edge/devices${query}`);
}

export async function getDevice(deviceId: string): Promise<EdgeDevice> {
  return apiJson<EdgeDevice>(`/api/edge/devices/${deviceId}`);
}

export async function updateDevice(
  deviceId: string,
  updates: {
    name?: string;
    status?: string;
    classification_level?: string;
    config_version?: string;
    metadata?: Record<string, unknown>;
  }
): Promise<EdgeDevice> {
  return apiJson<EdgeDevice>(`/api/edge/devices/${deviceId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

export async function revokeDevice(deviceId: string): Promise<void> {
  await apiFetch(`/api/edge/devices/${deviceId}`, {
    method: "DELETE",
  });
}
