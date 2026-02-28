"use client";

import { useState } from "react";

interface ThinkingBlockProps {
  content: string;
}

export function ThinkingBlock({ content }: ThinkingBlockProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 border border-[var(--color-border)] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
      >
        <span className="text-[var(--color-accent)]">{expanded ? "v" : ">"}</span>
        <span>Thinking</span>
        <span className="ml-auto text-[10px]">
          {content.length} chars
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)] border-t border-[var(--color-border)] whitespace-pre-wrap max-h-64 overflow-y-auto">
          {content}
        </div>
      )}
    </div>
  );
}
