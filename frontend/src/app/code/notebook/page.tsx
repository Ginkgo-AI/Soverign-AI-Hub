"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import {
  NotebookCell,
  type CellData,
  type CellType,
} from "@/components/code/NotebookCell";
import { executeCode } from "@/lib/code";

let cellCounter = 0;
function newCellId(): string {
  cellCounter += 1;
  return `cell-${Date.now()}-${cellCounter}`;
}

function createCell(type: CellType = "code", source: string = ""): CellData {
  return {
    id: newCellId(),
    type,
    source,
    output: "",
    stderr: "",
    executionCount: null,
    executionTimeMs: 0,
    isRunning: false,
    isEditing: type === "code",
  };
}

export default function NotebookPage() {
  const { loadFromStorage } = useAuthStore();

  const [cells, setCells] = useState<CellData[]>([
    createCell("code", '# Welcome to the Code Notebook\nprint("Hello, world!")'),
  ]);
  const [language, setLanguage] = useState("python");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [executionCounter, setExecutionCounter] = useState(0);
  const [isRunningAll, setIsRunningAll] = useState(false);

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  const updateCell = useCallback(
    (id: string, updates: Partial<CellData>) => {
      setCells((prev) =>
        prev.map((c) => (c.id === id ? { ...c, ...updates } : c))
      );
    },
    []
  );

  const handleSourceChange = useCallback(
    (id: string, source: string) => {
      updateCell(id, { source });
    },
    [updateCell]
  );

  const handleRunCell = useCallback(
    async (id: string) => {
      const cell = cells.find((c) => c.id === id);
      if (!cell || cell.type !== "code" || !cell.source.trim()) return;

      updateCell(id, { isRunning: true, output: "", stderr: "" });
      const nextCount = executionCounter + 1;
      setExecutionCounter(nextCount);

      try {
        const result = await executeCode(
          cell.source,
          language,
          sessionId || undefined
        );

        updateCell(id, {
          isRunning: false,
          output: result.stdout,
          stderr: result.stderr,
          executionCount: nextCount,
          executionTimeMs: result.execution_time_ms,
        });

        if (result.session_id) {
          setSessionId(result.session_id);
        }
      } catch (err) {
        updateCell(id, {
          isRunning: false,
          stderr: err instanceof Error ? err.message : "Execution failed",
          executionCount: nextCount,
        });
      }
    },
    [cells, language, sessionId, executionCounter, updateCell]
  );

  const handleRunAll = useCallback(async () => {
    setIsRunningAll(true);
    const codeCells = cells.filter((c) => c.type === "code");
    for (const cell of codeCells) {
      await handleRunCell(cell.id);
    }
    setIsRunningAll(false);
  }, [cells, handleRunCell]);

  const handleAddCell = useCallback(
    (type: CellType = "code", afterId?: string) => {
      const newCell = createCell(type);
      setCells((prev) => {
        if (afterId) {
          const idx = prev.findIndex((c) => c.id === afterId);
          if (idx >= 0) {
            return [...prev.slice(0, idx + 1), newCell, ...prev.slice(idx + 1)];
          }
        }
        return [...prev, newCell];
      });
    },
    []
  );

  const handleDeleteCell = useCallback((id: string) => {
    setCells((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((c) => c.id !== id);
    });
  }, []);

  const handleMoveUp = useCallback((id: string) => {
    setCells((prev) => {
      const idx = prev.findIndex((c) => c.id === id);
      if (idx <= 0) return prev;
      const newCells = [...prev];
      [newCells[idx - 1], newCells[idx]] = [newCells[idx], newCells[idx - 1]];
      return newCells;
    });
  }, []);

  const handleMoveDown = useCallback((id: string) => {
    setCells((prev) => {
      const idx = prev.findIndex((c) => c.id === id);
      if (idx < 0 || idx >= prev.length - 1) return prev;
      const newCells = [...prev];
      [newCells[idx], newCells[idx + 1]] = [newCells[idx + 1], newCells[idx]];
      return newCells;
    });
  }, []);

  const handleChangeType = useCallback(
    (id: string, type: CellType) => {
      updateCell(id, { type, isEditing: type === "code" });
    },
    [updateCell]
  );

  const handleToggleEdit = useCallback(
    (id: string) => {
      const cell = cells.find((c) => c.id === id);
      if (cell) {
        updateCell(id, { isEditing: !cell.isEditing });
      }
    },
    [cells, updateCell]
  );

  const handleClearOutputs = useCallback(() => {
    setCells((prev) =>
      prev.map((c) => ({
        ...c,
        output: "",
        stderr: "",
        executionCount: null,
        executionTimeMs: 0,
      }))
    );
    setExecutionCounter(0);
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)] shrink-0">
        <div className="flex items-center gap-3">
          <a
            href="/code"
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            &#8592; Code Editor
          </a>
          <h2 className="text-sm font-medium">Notebook</h2>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="px-2 py-1 text-xs rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)]"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="bash">Bash</option>
            <option value="sql">SQL</option>
          </select>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {cells.length} cell{cells.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunAll}
            disabled={isRunningAll}
            className="px-3 py-1 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
          >
            {isRunningAll ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running All...
              </>
            ) : (
              <>&#9654;&#9654; Run All</>
            )}
          </button>
          <button
            onClick={handleClearOutputs}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            Clear Outputs
          </button>
          <button
            onClick={() => handleAddCell("code")}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            + Code
          </button>
          <button
            onClick={() => handleAddCell("markdown")}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            + Markdown
          </button>
        </div>
      </div>

      {/* Notebook cells */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="max-w-4xl mx-auto space-y-3">
          {cells.map((cell, index) => (
            <div key={cell.id}>
              <NotebookCell
                cell={cell}
                index={index}
                totalCells={cells.length}
                language={language}
                onSourceChange={handleSourceChange}
                onRun={handleRunCell}
                onDelete={handleDeleteCell}
                onMoveUp={handleMoveUp}
                onMoveDown={handleMoveDown}
                onChangeType={handleChangeType}
                onToggleEdit={handleToggleEdit}
              />
              {/* Add cell button between cells */}
              <div className="flex justify-center py-1 opacity-0 hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleAddCell("code", cell.id)}
                  className="px-3 py-0.5 text-[10px] rounded-full border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)] transition-colors"
                >
                  + Add Cell
                </button>
              </div>
            </div>
          ))}

          {cells.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm text-[var(--color-text-muted)] mb-4">
                No cells yet. Add a cell to get started.
              </p>
              <button
                onClick={() => handleAddCell("code")}
                className="px-4 py-2 text-sm rounded bg-[var(--color-accent)] text-white hover:opacity-90"
              >
                + Add Code Cell
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
