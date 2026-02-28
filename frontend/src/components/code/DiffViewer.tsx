"use client";

import { useState, useMemo } from "react";

interface DiffViewerProps {
  diff: string;
}

interface DiffLine {
  type: "add" | "remove" | "context" | "header" | "meta";
  content: string;
  oldLine: number | null;
  newLine: number | null;
}

function parseDiff(diff: string): DiffLine[] {
  const lines: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;

  for (const raw of diff.split("\n")) {
    if (raw.startsWith("diff --git") || raw.startsWith("index ")) {
      lines.push({ type: "meta", content: raw, oldLine: null, newLine: null });
    } else if (raw.startsWith("@@")) {
      // Parse hunk header: @@ -old,len +new,len @@
      const match = raw.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLine = parseInt(match[1], 10);
        newLine = parseInt(match[2], 10);
      }
      lines.push({ type: "header", content: raw, oldLine: null, newLine: null });
    } else if (raw.startsWith("---") || raw.startsWith("+++")) {
      lines.push({ type: "meta", content: raw, oldLine: null, newLine: null });
    } else if (raw.startsWith("+")) {
      lines.push({ type: "add", content: raw, oldLine: null, newLine: newLine });
      newLine++;
    } else if (raw.startsWith("-")) {
      lines.push({ type: "remove", content: raw, oldLine: oldLine, newLine: null });
      oldLine++;
    } else {
      lines.push({ type: "context", content: raw, oldLine: oldLine, newLine: newLine });
      oldLine++;
      newLine++;
    }
  }

  return lines;
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<"unified" | "side">("unified");
  const lines = useMemo(() => parseDiff(diff), [diff]);

  if (!diff.trim()) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs text-[var(--color-text-muted)]">No diff to display</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border border-[var(--color-border)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <span className="text-xs font-medium text-[var(--color-text-muted)]">
          Diff Viewer
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewMode("unified")}
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              viewMode === "unified"
                ? "bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            Unified
          </button>
          <button
            onClick={() => setViewMode("side")}
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              viewMode === "side"
                ? "bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            Side by Side
          </button>
        </div>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto bg-[#0d1117]">
        {viewMode === "unified" ? (
          <UnifiedView lines={lines} />
        ) : (
          <SideBySideView lines={lines} />
        )}
      </div>
    </div>
  );
}

function UnifiedView({ lines }: { lines: DiffLine[] }) {
  return (
    <table className="w-full text-xs font-mono">
      <tbody>
        {lines.map((line, i) => (
          <tr
            key={i}
            className={
              line.type === "add"
                ? "bg-green-950/40"
                : line.type === "remove"
                  ? "bg-red-950/40"
                  : line.type === "header"
                    ? "bg-blue-950/30"
                    : line.type === "meta"
                      ? "bg-[var(--color-surface)]/30"
                      : ""
            }
          >
            <td className="select-none text-right px-2 py-0 text-[var(--color-text-muted)]/40 w-10 align-top">
              {line.oldLine ?? ""}
            </td>
            <td className="select-none text-right px-2 py-0 text-[var(--color-text-muted)]/40 w-10 align-top">
              {line.newLine ?? ""}
            </td>
            <td className="px-2 py-0 whitespace-pre-wrap break-all">
              <span
                className={
                  line.type === "add"
                    ? "text-green-400"
                    : line.type === "remove"
                      ? "text-red-400"
                      : line.type === "header"
                        ? "text-blue-400"
                        : line.type === "meta"
                          ? "text-[var(--color-text-muted)]"
                          : "text-[var(--color-text)]"
                }
              >
                {line.content}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SideBySideView({ lines }: { lines: DiffLine[] }) {
  // Build paired lines for side-by-side
  const leftLines: (DiffLine | null)[] = [];
  const rightLines: (DiffLine | null)[] = [];

  for (const line of lines) {
    if (line.type === "remove") {
      leftLines.push(line);
      rightLines.push(null);
    } else if (line.type === "add") {
      leftLines.push(null);
      rightLines.push(line);
    } else {
      leftLines.push(line);
      rightLines.push(line);
    }
  }

  return (
    <div className="flex">
      {/* Left (old) */}
      <div className="flex-1 border-r border-[var(--color-border)]/30">
        <table className="w-full text-xs font-mono">
          <tbody>
            {leftLines.map((line, i) => (
              <tr
                key={i}
                className={
                  line?.type === "remove"
                    ? "bg-red-950/40"
                    : line?.type === "header"
                      ? "bg-blue-950/30"
                      : ""
                }
              >
                <td className="select-none text-right px-2 py-0 text-[var(--color-text-muted)]/40 w-10">
                  {line?.oldLine ?? ""}
                </td>
                <td className="px-2 py-0 whitespace-pre-wrap break-all">
                  <span
                    className={
                      line?.type === "remove"
                        ? "text-red-400"
                        : line?.type === "header" || line?.type === "meta"
                          ? "text-[var(--color-text-muted)]"
                          : "text-[var(--color-text)]"
                    }
                  >
                    {line?.content ?? ""}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Right (new) */}
      <div className="flex-1">
        <table className="w-full text-xs font-mono">
          <tbody>
            {rightLines.map((line, i) => (
              <tr
                key={i}
                className={
                  line?.type === "add"
                    ? "bg-green-950/40"
                    : line?.type === "header"
                      ? "bg-blue-950/30"
                      : ""
                }
              >
                <td className="select-none text-right px-2 py-0 text-[var(--color-text-muted)]/40 w-10">
                  {line?.newLine ?? ""}
                </td>
                <td className="px-2 py-0 whitespace-pre-wrap break-all">
                  <span
                    className={
                      line?.type === "add"
                        ? "text-green-400"
                        : line?.type === "header" || line?.type === "meta"
                          ? "text-[var(--color-text-muted)]"
                          : "text-[var(--color-text)]"
                    }
                  >
                    {line?.content ?? ""}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
