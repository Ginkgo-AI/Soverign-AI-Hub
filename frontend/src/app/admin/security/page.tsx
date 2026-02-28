"use client";

import { useEffect, useState } from "react";
import {
  getSecurityConfig,
  updateSecurityConfig,
  type SecurityConfig,
} from "@/lib/admin";

export default function SecurityPage() {
  const [config, setConfig] = useState<SecurityConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await getSecurityConfig();
      setConfig(data);
    } catch (e: any) {
      setError(e.message || "Failed to load security config");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateSecurityConfig({
        airgap_mode: config.airgap_mode,
        session_timeout_minutes: config.session_timeout_minutes,
        max_concurrent_sessions: config.max_concurrent_sessions,
        audit_retention_days: config.audit_retention_days,
        siem_endpoint: config.siem_endpoint,
      });
      setConfig(updated);
      setSuccess("Configuration saved successfully.");
    } catch (e: any) {
      setError(e.message || "Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-[var(--color-text-muted)]">
        Loading security configuration...
      </div>
    );
  }

  if (!config) {
    return (
      <div className="p-6 text-red-400">
        Failed to load configuration. {error}
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h2 className="text-2xl font-semibold">Security Configuration</h2>

      {error && (
        <div className="p-3 text-sm bg-red-900/30 border border-red-700 rounded text-red-300">
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 text-sm bg-green-900/30 border border-green-700 rounded text-green-300">
          {success}
        </div>
      )}

      {/* Status cards */}
      <div className="grid grid-cols-3 gap-4">
        <StatusCard
          label="Encryption"
          value={config.encryption_enabled ? "Enabled" : "Default key"}
          ok={config.encryption_enabled}
        />
        <StatusCard
          label="Keycloak"
          value={config.keycloak_enabled ? "Connected" : "Not configured"}
          ok={config.keycloak_enabled}
        />
        <StatusCard
          label="Air-Gap Mode"
          value={config.airgap_mode ? "Enabled" : "Disabled"}
          ok={config.airgap_mode}
        />
      </div>

      {/* Classification levels */}
      <Section title="Classification Levels">
        <div className="flex gap-2 flex-wrap">
          {config.classification_levels.map((level) => (
            <span
              key={level}
              className="px-2 py-1 text-xs font-semibold rounded border border-[var(--color-border)] bg-[var(--color-surface)]"
            >
              {level}
            </span>
          ))}
        </div>
      </Section>

      {/* Air-gap toggle */}
      <Section title="Network">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={config.airgap_mode}
            onChange={(e) =>
              setConfig({ ...config, airgap_mode: e.target.checked })
            }
            className="w-4 h-4"
          />
          <span className="text-sm">
            Air-gap mode (block all external network connections)
          </span>
        </label>
      </Section>

      {/* Session settings */}
      <Section title="Session Settings">
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-xs text-[var(--color-text-muted)]">
              Session timeout (minutes)
            </span>
            <input
              type="number"
              value={config.session_timeout_minutes}
              onChange={(e) =>
                setConfig({
                  ...config,
                  session_timeout_minutes: parseInt(e.target.value) || 1440,
                })
              }
              className="w-full px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-[var(--color-text-muted)]">
              Max concurrent sessions
            </span>
            <input
              type="number"
              value={config.max_concurrent_sessions}
              onChange={(e) =>
                setConfig({
                  ...config,
                  max_concurrent_sessions: parseInt(e.target.value) || 5,
                })
              }
              className="w-full px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
            />
          </label>
        </div>
      </Section>

      {/* Audit settings */}
      <Section title="Audit & SIEM">
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-xs text-[var(--color-text-muted)]">
              Audit log retention (days)
            </span>
            <input
              type="number"
              value={config.audit_retention_days}
              onChange={(e) =>
                setConfig({
                  ...config,
                  audit_retention_days: parseInt(e.target.value) || 365,
                })
              }
              className="w-full max-w-xs px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-[var(--color-text-muted)]">
              SIEM endpoint (syslog/webhook URL)
            </span>
            <input
              type="text"
              value={config.siem_endpoint}
              onChange={(e) =>
                setConfig({ ...config, siem_endpoint: e.target.value })
              }
              placeholder="e.g., syslog://splunk.internal:514"
              className="w-full px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
            />
          </label>
        </div>
      </Section>

      {/* SBOM */}
      <Section title="Software Bill of Materials">
        <p className="text-sm text-[var(--color-text-muted)]">
          Generate an SBOM using the server-side script:
        </p>
        <code className="block mt-2 p-2 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded font-mono">
          ./scripts/generate-sbom.sh
        </code>
      </Section>

      <button
        onClick={handleSave}
        disabled={saving}
        className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Configuration"}
      </button>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] space-y-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  );
}

function StatusCard({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 text-sm font-medium flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${
            ok ? "bg-green-500" : "bg-yellow-500"
          }`}
        />
        {value}
      </p>
    </div>
  );
}
