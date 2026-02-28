"use client";

import { useState } from "react";

interface OutputPanelProps {
  stdout: string;
  stderr: string;
  returnValue: string | null;
  executionTimeMs: number;
  exitCode: number;
  onClear: () => void;
}

type OutputTab = "stdout" | "stderr" | "return";

export function OutputPanel({
  stdout,
  stderr,
  returnValue,
  executionTimeMs,
  exitCode,
  onClear,
}: OutputPanelProps) {
  const [activeTab, setActiveTab] = useState<OutputTab>("stdout");

  const tabs: { key: OutputTab; label: string; hasContent: boolean }[] = [
    { key: "stdout", label: "Output", hasContent: !!stdout },
    { key: "stderr", label: "Errors", hasContent: !!stderr },
    { key: "return", label: "Return Value", hasContent: returnValue !== null },
  ];

  const content =
    activeTab === "stdout"
      ? stdout
      : activeTab === "stderr"
        ? stderr
        : returnValue || "";

  const hasAnyOutput = stdout || stderr || returnValue;

  return (
    <div className="flex flex-col h-full border border-[var(--color-border)] rounded-lg overflow-hidden bg-[#0d1117]">
      {/* Tab bar */}
      <div className="flex items-center justify-between px-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-2 text-xs transition-colors relative ${
                activeTab === tab.key
                  ? "text-[var(--color-text)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {tab.label}
              {tab.hasContent && tab.key === "stderr" && (
                <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-red-500" />
              )}
              {activeTab === tab.key && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)]" />
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {executionTimeMs > 0 && (
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {executionTimeMs < 1000
                ? `${Math.round(executionTimeMs)}ms`
                : `${(executionTimeMs / 1000).toFixed(2)}s`}
              {exitCode !== 0 && (
                <span className="ml-1 text-red-400">
                  exit: {exitCode}
                </span>
              )}
            </span>
          )}
          <button
            onClick={onClear}
            className="px-2 py-1 text-[10px] rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        {hasAnyOutput ? (
          <pre className="text-xs font-mono leading-relaxed text-[var(--color-text)] whitespace-pre-wrap break-words">
            {content || (
              <span className="text-[var(--color-text-muted)] italic">
                No {activeTab === "stderr" ? "errors" : "output"}
              </span>
            )}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-xs text-[var(--color-text-muted)]">
              Run code to see output here
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
