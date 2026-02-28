"use client";

import { useEffect, useState } from "react";
import {
  listDevices,
  registerDevice,
  revokeDevice,
  updateDevice,
  type EdgeDevice,
  type EdgeDeviceWithKey,
} from "@/lib/edge";

export default function EdgeDevicesPage() {
  const [devices, setDevices] = useState<EdgeDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Registration modal
  const [showRegister, setShowRegister] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAgentId, setNewAgentId] = useState("");
  const [newClassification, setNewClassification] = useState("UNCLASSIFIED");
  const [registering, setRegistering] = useState(false);
  const [registeredDevice, setRegisteredDevice] =
    useState<EdgeDeviceWithKey | null>(null);

  // Detail panel
  const [selected, setSelected] = useState<EdgeDevice | null>(null);

  useEffect(() => {
    loadDevices();
  }, []);

  const loadDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDevices();
      setDevices(data.devices);
    } catch (e: any) {
      setError(e.message || "Failed to load edge devices");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!newName.trim()) return;
    setRegistering(true);
    setError(null);
    try {
      const device = await registerDevice(newName, {
        agent_id: newAgentId || undefined,
        classification_level: newClassification,
      });
      setRegisteredDevice(device);
      await loadDevices();
    } catch (e: any) {
      setError(e.message || "Failed to register device");
    } finally {
      setRegistering(false);
    }
  };

  const handleRevoke = async (deviceId: string) => {
    if (!confirm("Revoke this device? It will no longer be able to sync."))
      return;
    try {
      await revokeDevice(deviceId);
      await loadDevices();
      if (selected?.id === deviceId) setSelected(null);
    } catch (e: any) {
      setError(e.message || "Failed to revoke device");
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-[var(--color-text-muted)]">
        Loading edge devices...
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Edge Devices</h2>
        <button
          onClick={() => {
            setShowRegister(true);
            setRegisteredDevice(null);
            setNewName("");
            setNewAgentId("");
            setNewClassification("UNCLASSIFIED");
          }}
          className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded"
        >
          Register Device
        </button>
      </div>

      {error && (
        <div className="p-3 text-sm bg-red-900/30 border border-red-700 rounded text-red-300">
          {error}
        </div>
      )}

      {/* Registration modal */}
      {showRegister && (
        <div className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] space-y-4">
          {registeredDevice ? (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-green-400">
                Device Registered Successfully
              </h3>
              <p className="text-xs text-[var(--color-text-muted)]">
                Copy the API key below. It will not be shown again.
              </p>
              <div className="p-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded font-mono text-xs break-all">
                {registeredDevice.api_key}
              </div>
              <div className="text-xs text-[var(--color-text-muted)] space-y-1">
                <p>
                  Agent ID:{" "}
                  <span className="font-mono">
                    {registeredDevice.agent_id}
                  </span>
                </p>
                <p>
                  Configure the edge agent with:
                </p>
                <code className="block mt-1 p-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded">
                  sovereign-edge config hub_url
                  https://your-hub-address:8888
                  <br />
                  sovereign-edge config agent_id{" "}
                  {registeredDevice.agent_id}
                  <br />
                  sovereign-edge config api_key YOUR_API_KEY
                </code>
              </div>
              <button
                onClick={() => setShowRegister(false)}
                className="px-3 py-1.5 text-sm bg-[var(--color-surface-hover)] hover:bg-[var(--color-border)] rounded"
              >
                Close
              </button>
            </div>
          ) : (
            <>
              <h3 className="text-sm font-semibold">Register New Edge Device</h3>
              <div className="grid grid-cols-3 gap-4">
                <label className="space-y-1">
                  <span className="text-xs text-[var(--color-text-muted)]">
                    Device Name *
                  </span>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g., Field Station Alpha"
                    className="w-full px-2 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--color-text-muted)]">
                    Agent ID (auto if blank)
                  </span>
                  <input
                    type="text"
                    value={newAgentId}
                    onChange={(e) => setNewAgentId(e.target.value)}
                    placeholder="edge-alpha-01"
                    className="w-full px-2 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--color-text-muted)]">
                    Classification
                  </span>
                  <select
                    value={newClassification}
                    onChange={(e) => setNewClassification(e.target.value)}
                    className="w-full px-2 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded"
                  >
                    <option value="UNCLASSIFIED">UNCLASSIFIED</option>
                    <option value="CUI">CUI</option>
                    <option value="FOUO">FOUO</option>
                    <option value="SECRET">SECRET</option>
                  </select>
                </label>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleRegister}
                  disabled={registering || !newName.trim()}
                  className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
                >
                  {registering ? "Registering..." : "Register"}
                </button>
                <button
                  onClick={() => setShowRegister(false)}
                  className="px-4 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Devices table */}
      <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--color-surface)] text-left text-xs text-[var(--color-text-muted)]">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Agent ID</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Last Seen</th>
              <th className="px-4 py-3 font-medium">Classification</th>
              <th className="px-4 py-3 font-medium">Sync</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {devices.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-[var(--color-text-muted)]"
                >
                  No edge devices registered.
                </td>
              </tr>
            ) : (
              devices.map((device) => (
                <tr
                  key={device.id}
                  className="hover:bg-[var(--color-surface-hover)] cursor-pointer"
                  onClick={() => setSelected(device)}
                >
                  <td className="px-4 py-3 font-medium">{device.name}</td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {device.agent_id}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={device.status} lastSeen={device.last_seen} />
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                    {device.last_seen
                      ? new Date(device.last_seen).toLocaleString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 text-xs font-semibold rounded border border-[var(--color-border)]">
                      {device.classification_level}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <SyncSummary syncState={device.sync_state} />
                  </td>
                  <td className="px-4 py-3">
                    {device.status !== "revoked" && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRevoke(device.id);
                        }}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail panel */}
      {selected && (
        <DeviceDetailPanel
          device={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({
  status,
  lastSeen,
}: {
  status: string;
  lastSeen: string | null;
}) {
  let color = "bg-gray-500";
  let label = status;

  if (status === "revoked") {
    color = "bg-red-500";
  } else if (status === "active") {
    if (lastSeen) {
      const delta =
        (Date.now() - new Date(lastSeen).getTime()) / 1000;
      if (delta < 600) {
        color = "bg-green-500";
        label = "online";
      } else if (delta < 3600) {
        color = "bg-yellow-500";
        label = "stale";
      } else {
        color = "bg-red-500";
        label = "offline";
      }
    } else {
      color = "bg-gray-500";
      label = "never seen";
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}

function SyncSummary({
  syncState,
}: {
  syncState: Record<string, { last_sync: string; items: number; status: string }> | null;
}) {
  if (!syncState || Object.keys(syncState).length === 0) {
    return (
      <span className="text-xs text-[var(--color-text-muted)]">No syncs</span>
    );
  }

  // Find most recent sync
  let mostRecent = "";
  let mostRecentTime = 0;
  for (const [key, entry] of Object.entries(syncState)) {
    const t = new Date(entry.last_sync).getTime();
    if (t > mostRecentTime) {
      mostRecentTime = t;
      mostRecent = key;
    }
  }

  const ago = timeSince(new Date(mostRecentTime));
  return (
    <span className="text-xs text-[var(--color-text-muted)]">
      {mostRecent}: {ago}
    </span>
  );
}

function DeviceDetailPanel({
  device,
  onClose,
}: {
  device: EdgeDevice;
  onClose: () => void;
}) {
  return (
    <div className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{device.name}</h3>
        <button
          onClick={onClose}
          className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          Close
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-[var(--color-text-muted)]">Agent ID</span>
          <p className="font-mono mt-0.5">{device.agent_id}</p>
        </div>
        <div>
          <span className="text-[var(--color-text-muted)]">Status</span>
          <p className="mt-0.5">{device.status}</p>
        </div>
        <div>
          <span className="text-[var(--color-text-muted)]">Config Version</span>
          <p className="mt-0.5">{device.config_version}</p>
        </div>
        <div>
          <span className="text-[var(--color-text-muted)]">Created</span>
          <p className="mt-0.5">
            {new Date(device.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Sync state timeline */}
      {device.sync_state && Object.keys(device.sync_state).length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-muted)] mb-2">
            Sync History
          </h4>
          <div className="space-y-2">
            {Object.entries(device.sync_state).map(([key, entry]) => (
              <div
                key={key}
                className="flex items-center justify-between text-xs p-2 bg-[var(--color-bg)] rounded"
              >
                <span className="font-medium">{key}</span>
                <span className="text-[var(--color-text-muted)]">
                  {entry.items} items &middot;{" "}
                  {new Date(entry.last_sync).toLocaleString()} &middot;{" "}
                  <span
                    className={
                      entry.status === "success"
                        ? "text-green-400"
                        : "text-red-400"
                    }
                  >
                    {entry.status}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeSince(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
