"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

interface ToolInfo {
  name: string;
  description: string;
  category: string;
}

interface ToolPickerProps {
  enabledTools: string[];
  onToolsChange: (tools: string[]) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  code_execution: "Code",
  file_ops: "Files",
  search: "Search",
  data_analysis: "Data",
  http: "HTTP",
  multimodal: "Multimodal",
};

export function ToolPicker({ enabledTools, onToolsChange }: ToolPickerProps) {
  const [open, setOpen] = useState(false);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [open]);

  // Fetch tool list when opening
  const fetchTools = useCallback(async () => {
    if (tools.length > 0) return;
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/api/agents/tools`, { headers });
      if (res.ok) {
        const data = await res.json();
        setTools(data.tools || []);
      }
    } catch {
      // Silently fail — tools will show as empty
    } finally {
      setLoading(false);
    }
  }, [tools.length]);

  const handleToggle = useCallback(() => {
    setOpen((prev) => {
      if (!prev) fetchTools();
      return !prev;
    });
  }, [fetchTools]);

  const toggleTool = useCallback(
    (name: string) => {
      if (enabledTools.includes(name)) {
        onToolsChange(enabledTools.filter((t) => t !== name));
      } else {
        onToolsChange([...enabledTools, name]);
      }
    },
    [enabledTools, onToolsChange]
  );

  // Group tools by category
  const grouped = tools.reduce<Record<string, ToolInfo[]>>((acc, tool) => {
    const cat = tool.category || "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(tool);
    return acc;
  }, {});

  const activeCount = enabledTools.length;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleToggle}
        className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-[var(--color-text-muted)]"
        title="Configure tools"
      >
        <span>{"\u2699"}</span>
        <span>Tools</span>
        {activeCount > 0 && (
          <span className="ml-0.5 px-1 py-px text-[10px] rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
            {activeCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 max-h-80 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg z-50">
          <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center justify-between">
            <span className="text-xs font-semibold">Available Tools</span>
            {enabledTools.length > 0 && (
              <button
                onClick={() => onToolsChange([])}
                className="text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                Use defaults
              </button>
            )}
          </div>

          {loading ? (
            <div className="px-3 py-4 text-xs text-[var(--color-text-muted)] text-center">
              Loading tools...
            </div>
          ) : tools.length === 0 ? (
            <div className="px-3 py-4 text-xs text-[var(--color-text-muted)] text-center">
              No tools available. Ensure gateway is running.
            </div>
          ) : (
            Object.entries(grouped).map(([category, categoryTools]) => (
              <div key={category}>
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-muted)] bg-[var(--color-bg)]">
                  {CATEGORY_LABELS[category] || category}
                </div>
                {categoryTools.map((tool) => {
                  const isActive =
                    enabledTools.length === 0 || enabledTools.includes(tool.name);
                  return (
                    <label
                      key={tool.name}
                      className="flex items-start gap-2 px-3 py-1.5 hover:bg-[var(--color-surface-hover)] cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={isActive}
                        onChange={() => toggleTool(tool.name)}
                        className="mt-0.5 accent-[var(--color-accent)]"
                      />
                      <div className="min-w-0">
                        <div className="text-xs font-medium">{tool.name}</div>
                        <div className="text-[10px] text-[var(--color-text-muted)] leading-tight truncate">
                          {tool.description}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
