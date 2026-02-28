"use client";

import { useCallback, useRef, KeyboardEvent } from "react";

export type CellType = "code" | "markdown";

export interface CellData {
  id: string;
  type: CellType;
  source: string;
  output: string;
  stderr: string;
  executionCount: number | null;
  executionTimeMs: number;
  isRunning: boolean;
  isEditing: boolean;
}

interface NotebookCellProps {
  cell: CellData;
  index: number;
  totalCells: number;
  language: string;
  onSourceChange: (id: string, source: string) => void;
  onRun: (id: string) => void;
  onDelete: (id: string) => void;
  onMoveUp: (id: string) => void;
  onMoveDown: (id: string) => void;
  onChangeType: (id: string, type: CellType) => void;
  onToggleEdit: (id: string) => void;
}

export function NotebookCell({
  cell,
  index,
  totalCells,
  language,
  onSourceChange,
  onRun,
  onDelete,
  onMoveUp,
  onMoveDown,
  onChangeType,
  onToggleEdit,
}: NotebookCellProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const textarea = e.currentTarget;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const newValue =
          cell.source.substring(0, start) +
          "    " +
          cell.source.substring(end);
        onSourceChange(cell.id, newValue);
        requestAnimationFrame(() => {
          textarea.selectionStart = start + 4;
          textarea.selectionEnd = start + 4;
        });
      }
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        onRun(cell.id);
      }
    },
    [cell.id, cell.source, onSourceChange, onRun]
  );

  const lineCount = cell.source.split("\n").length;
  const rows = Math.max(3, Math.min(lineCount + 1, 30));

  return (
    <div className="group border border-[var(--color-border)] rounded-lg overflow-hidden bg-[var(--color-surface)] hover:border-[var(--color-accent)]/30 transition-colors">
      {/* Cell toolbar */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2">
          {/* Execution counter */}
          <span className="text-[10px] font-mono text-[var(--color-text-muted)] w-8">
            {cell.type === "code"
              ? cell.executionCount !== null
                ? `[${cell.executionCount}]`
                : "[ ]"
              : ""}
          </span>

          {/* Cell type */}
          <select
            value={cell.type}
            onChange={(e) =>
              onChangeType(cell.id, e.target.value as CellType)
            }
            className="px-1 py-0.5 text-[10px] rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text-muted)]"
          >
            <option value="code">Code</option>
            <option value="markdown">Markdown</option>
          </select>

          {cell.isRunning && (
            <span className="inline-block w-3 h-3 border-2 border-[var(--color-accent)]/30 border-t-[var(--color-accent)] rounded-full animate-spin" />
          )}

          {cell.executionTimeMs > 0 && (
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {cell.executionTimeMs < 1000
                ? `${Math.round(cell.executionTimeMs)}ms`
                : `${(cell.executionTimeMs / 1000).toFixed(2)}s`}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {cell.type === "code" && (
            <button
              onClick={() => onRun(cell.id)}
              disabled={cell.isRunning}
              className="px-2 py-0.5 text-[10px] rounded bg-[var(--color-accent)] text-white disabled:opacity-50"
              title="Run (Ctrl+Enter)"
            >
              &#9654; Run
            </button>
          )}
          {cell.type === "markdown" && (
            <button
              onClick={() => onToggleEdit(cell.id)}
              className="px-2 py-0.5 text-[10px] rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              {cell.isEditing ? "Preview" : "Edit"}
            </button>
          )}
          <button
            onClick={() => onMoveUp(cell.id)}
            disabled={index === 0}
            className="px-1 py-0.5 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
            title="Move up"
          >
            &#9650;
          </button>
          <button
            onClick={() => onMoveDown(cell.id)}
            disabled={index === totalCells - 1}
            className="px-1 py-0.5 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
            title="Move down"
          >
            &#9660;
          </button>
          <button
            onClick={() => onDelete(cell.id)}
            className="px-1 py-0.5 text-[10px] text-red-400 hover:text-red-300"
            title="Delete cell"
          >
            &#10005;
          </button>
        </div>
      </div>

      {/* Cell content */}
      <div className="relative">
        {cell.type === "code" || cell.isEditing ? (
          <div className="flex bg-[#0d1117]">
            {/* Line numbers */}
            <div className="select-none text-right pr-3 pl-2 pt-2 pb-2 text-[10px] font-mono text-[var(--color-text-muted)]/40 leading-[1.4rem] shrink-0 border-r border-[var(--color-border)]/20">
              {Array.from({ length: lineCount }, (_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            <textarea
              ref={textareaRef}
              value={cell.source}
              onChange={(e) => onSourceChange(cell.id, e.target.value)}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              rows={rows}
              className="flex-1 bg-transparent text-[var(--color-text)] font-mono text-xs p-2 resize-none outline-none leading-[1.4rem] placeholder:text-[var(--color-text-muted)]/40"
              placeholder={
                cell.type === "code"
                  ? `Enter ${language} code...`
                  : "Enter markdown..."
              }
              style={{ tabSize: 4 }}
            />
          </div>
        ) : (
          /* Markdown rendered */
          <div
            className="p-3 text-sm leading-relaxed text-[var(--color-text)] prose prose-invert max-w-none cursor-pointer"
            onClick={() => onToggleEdit(cell.id)}
          >
            {cell.source ? (
              <div className="whitespace-pre-wrap">{cell.source}</div>
            ) : (
              <p className="text-[var(--color-text-muted)] italic text-xs">
                Empty markdown cell (click to edit)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Output (code cells only) */}
      {cell.type === "code" && (cell.output || cell.stderr) && (
        <div className="border-t border-[var(--color-border)]/30 bg-[#0a0e14]">
          {cell.output && (
            <pre className="p-2 text-xs font-mono leading-relaxed text-[var(--color-text)] whitespace-pre-wrap overflow-x-auto max-h-64 overflow-y-auto">
              {cell.output}
            </pre>
          )}
          {cell.stderr && (
            <pre className="p-2 text-xs font-mono leading-relaxed text-red-400 whitespace-pre-wrap overflow-x-auto max-h-32 overflow-y-auto border-t border-red-500/20">
              {cell.stderr}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
