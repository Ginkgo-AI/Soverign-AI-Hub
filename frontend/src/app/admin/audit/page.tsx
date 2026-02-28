"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchAuditLogs,
  exportAuditLogs,
  type AuditEntry,
  type AuditFilters,
} from "@/lib/admin";

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterAction, setFilterAction] = useState("");
  const [filterResourceType, setFilterResourceType] = useState("");
  const [filterClassification, setFilterClassification] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterSearch, setFilterSearch] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: AuditFilters = {
        page,
        page_size: 50,
      };
      if (filterAction) filters.action = filterAction;
      if (filterResourceType) filters.resource_type = filterResourceType;
      if (filterClassification)
        filters.classification_level = filterClassification;
      if (filterDateFrom) filters.date_from = filterDateFrom;
      if (filterDateTo) filters.date_to = filterDateTo;
      if (filterSearch) filters.search = filterSearch;

      const data = await fetchAuditLogs(filters);
      setEntries(data.entries);
      setTotal(data.total);
      setPages(data.pages);
    } catch (e: any) {
      setError(e.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [
    page,
    filterAction,
    filterResourceType,
    filterClassification,
    filterDateFrom,
    filterDateTo,
    filterSearch,
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExport = async (format: "json" | "csv" | "syslog") => {
    try {
      const content = await exportAuditLogs(
        format,
        filterDateFrom || undefined,
        filterDateTo || undefined
      );
      const blob = new Blob([content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit_log.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || "Export failed");
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Audit Log</h2>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport("csv")}
            className="px-3 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded hover:bg-[var(--color-surface-hover)]"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport("json")}
            className="px-3 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded hover:bg-[var(--color-surface-hover)]"
          >
            Export JSON
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-6 gap-3">
        <input
          type="text"
          placeholder="Search..."
          value={filterSearch}
          onChange={(e) => {
            setFilterSearch(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        />
        <input
          type="text"
          placeholder="Action"
          value={filterAction}
          onChange={(e) => {
            setFilterAction(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        />
        <input
          type="text"
          placeholder="Resource type"
          value={filterResourceType}
          onChange={(e) => {
            setFilterResourceType(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        />
        <select
          value={filterClassification}
          onChange={(e) => {
            setFilterClassification(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        >
          <option value="">All Classifications</option>
          <option value="UNCLASSIFIED">UNCLASSIFIED</option>
          <option value="CUI">CUI</option>
          <option value="FOUO">FOUO</option>
          <option value="SECRET">SECRET</option>
          <option value="TOP_SECRET">TOP SECRET</option>
        </select>
        <input
          type="date"
          value={filterDateFrom}
          onChange={(e) => {
            setFilterDateFrom(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        />
        <input
          type="date"
          value={filterDateTo}
          onChange={(e) => {
            setFilterDateTo(e.target.value);
            setPage(1);
          }}
          className="px-2 py-1.5 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded"
        />
      </div>

      {error && (
        <div className="p-3 text-sm bg-red-900/30 border border-red-700 rounded text-red-300">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded border border-[var(--color-border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--color-surface)] text-left text-xs text-[var(--color-text-muted)]">
              <th className="px-3 py-2">Timestamp</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Resource</th>
              <th className="px-3 py-2">Classification</th>
              <th className="px-3 py-2">IP</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-[var(--color-text-muted)]">
                  Loading...
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-[var(--color-text-muted)]">
                  No audit records found.
                </td>
              </tr>
            ) : (
              entries.map((e) => (
                <tr
                  key={e.id}
                  className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
                >
                  <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-xs truncate max-w-[120px]">
                    {e.user_id ? e.user_id.slice(0, 8) + "..." : "-"}
                  </td>
                  <td className="px-3 py-2 text-xs">{e.action}</td>
                  <td className="px-3 py-2 text-xs">{e.resource_type}</td>
                  <td className="px-3 py-2">
                    <ClassificationBadge level={e.classification_level} />
                  </td>
                  <td className="px-3 py-2 text-xs font-mono">
                    {e.ip_address || "-"}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {e.response_summary?.match(/status=(\d+)/)?.[1] || "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-[var(--color-text-muted)]">
        <span>
          {total} total records {pages > 1 && `| Page ${page} of ${pages}`}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1 border border-[var(--color-border)] rounded disabled:opacity-40"
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages}
            className="px-3 py-1 border border-[var(--color-border)] rounded disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function ClassificationBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    UNCLASSIFIED: "bg-green-900/40 text-green-400 border-green-700",
    CUI: "bg-blue-900/40 text-blue-400 border-blue-700",
    FOUO: "bg-orange-900/40 text-orange-400 border-orange-700",
    SECRET: "bg-red-900/40 text-red-400 border-red-700",
    TOP_SECRET: "bg-yellow-900/40 text-yellow-400 border-yellow-700",
  };
  const cls = colors[level] || colors["UNCLASSIFIED"];
  return (
    <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded border ${cls}`}>
      {level}
    </span>
  );
}
