"use client";

import { useEffect, useState } from "react";
import {
  getComplianceReport,
  type ComplianceReport,
  type ComplianceControl,
} from "@/lib/admin";

const STATUS_COLORS: Record<string, string> = {
  implemented: "bg-green-500",
  partial: "bg-yellow-500",
  planned: "bg-orange-500",
  not_applicable: "bg-gray-500",
};

const STATUS_LABELS: Record<string, string> = {
  implemented: "Implemented",
  partial: "Partial",
  planned: "Planned",
  not_applicable: "N/A",
};

export default function CompliancePage() {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadReport();
  }, []);

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getComplianceReport();
      setReport(data);
    } catch (e: any) {
      setError(e.message || "Failed to load compliance report");
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDownload = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nist-800-53-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="p-6 text-[var(--color-text-muted)]">
        Generating compliance report...
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-6 text-red-400">
        Failed to generate report. {error}
      </div>
    );
  }

  // Group controls by family
  const families = new Map<string, ComplianceControl[]>();
  for (const ctrl of report.controls) {
    const list = families.get(ctrl.control_family) || [];
    list.push(ctrl);
    families.set(ctrl.control_family, list);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">
            NIST 800-53 Compliance Report
          </h2>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Generated: {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={handleDownload}
          className="px-3 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded hover:bg-[var(--color-surface-hover)]"
        >
          Download Report
        </button>
      </div>

      {/* Score overview */}
      <div className="grid grid-cols-4 gap-4">
        <ScoreCard
          label="Overall Score"
          value={`${report.overall_score}%`}
          color={
            report.overall_score >= 80
              ? "text-green-400"
              : report.overall_score >= 50
              ? "text-yellow-400"
              : "text-red-400"
          }
        />
        <ScoreCard
          label="Implemented"
          value={String(report.implemented)}
          color="text-green-400"
        />
        <ScoreCard
          label="Partial"
          value={String(report.partial)}
          color="text-yellow-400"
        />
        <ScoreCard
          label="Planned"
          value={String(report.planned)}
          color="text-orange-400"
        />
      </div>

      {/* Control families */}
      <div className="space-y-4">
        {Array.from(families.entries()).map(([family, controls]) => {
          const implemented = controls.filter(
            (c) => c.status === "implemented"
          ).length;
          const total = controls.length;
          return (
            <div
              key={family}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden"
            >
              <div className="px-4 py-3 flex items-center justify-between">
                <h3 className="font-medium text-sm">{family}</h3>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    {controls.map((c) => (
                      <span
                        key={c.control_id}
                        className={`w-3 h-3 rounded-full ${
                          STATUS_COLORS[c.status]
                        }`}
                        title={`${c.control_id}: ${STATUS_LABELS[c.status]}`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {implemented}/{total}
                  </span>
                </div>
              </div>
              <div className="border-t border-[var(--color-border)]">
                {controls.map((ctrl) => (
                  <div
                    key={ctrl.control_id}
                    className="border-b border-[var(--color-border)] last:border-0"
                  >
                    <button
                      onClick={() => toggleExpand(ctrl.control_id)}
                      className="w-full px-4 py-2 flex items-center justify-between text-left hover:bg-[var(--color-surface-hover)]"
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            STATUS_COLORS[ctrl.status]
                          }`}
                        />
                        <span className="text-xs font-mono text-[var(--color-text-muted)]">
                          {ctrl.control_id}
                        </span>
                        <span className="text-sm">{ctrl.control_name}</span>
                      </div>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {STATUS_LABELS[ctrl.status]}
                      </span>
                    </button>
                    {expanded.has(ctrl.control_id) && (
                      <div className="px-4 py-3 bg-[var(--color-bg)] text-sm space-y-2">
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                            Evidence:
                          </span>
                          <p className="mt-0.5">{ctrl.evidence}</p>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-[var(--color-text-muted)]">
                            Notes:
                          </span>
                          <p className="mt-0.5">{ctrl.notes}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ScoreCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-center">
      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
