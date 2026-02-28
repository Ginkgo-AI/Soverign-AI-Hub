"use client";

import { useCallback, useRef, KeyboardEvent } from "react";

interface CodeEditorProps {
  code: string;
  onChange: (code: string) => void;
  language: string;
  onLanguageChange: (lang: string) => void;
  onRun: () => void;
  onClear: () => void;
  isRunning: boolean;
  lineNumbers?: boolean;
}

const LANGUAGES = [
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "bash", label: "Bash" },
  { value: "sql", label: "SQL" },
];

export function CodeEditor({
  code,
  onChange,
  language,
  onLanguageChange,
  onRun,
  onClear,
  isRunning,
  lineNumbers = true,
}: CodeEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Tab key inserts spaces
      if (e.key === "Tab") {
        e.preventDefault();
        const textarea = e.currentTarget;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const newValue =
          code.substring(0, start) + "    " + code.substring(end);
        onChange(newValue);
        // Restore cursor position after React re-renders
        requestAnimationFrame(() => {
          textarea.selectionStart = start + 4;
          textarea.selectionEnd = start + 4;
        });
      }
      // Ctrl/Cmd + Enter to run
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        onRun();
      }
    },
    [code, onChange, onRun]
  );

  const lineCount = code.split("\n").length;
  const lineNums = Array.from({ length: lineCount }, (_, i) => i + 1);

  return (
    <div className="flex flex-col h-full border border-[var(--color-border)] rounded-lg overflow-hidden bg-[#0d1117]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="px-2 py-1 text-xs rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)]"
          >
            {LANGUAGES.map((lang) => (
              <option key={lang.value} value={lang.value}>
                {lang.label}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {lineCount} line{lineCount !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onClear}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            Clear
          </button>
          <button
            onClick={onRun}
            disabled={isRunning || !code.trim()}
            className="px-3 py-1 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          >
            {isRunning ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running...
              </>
            ) : (
              <>
                <span className="text-sm">&#9654;</span> Run
              </>
            )}
          </button>
        </div>
      </div>

      {/* Editor area */}
      <div className="flex-1 flex overflow-auto">
        {/* Line numbers */}
        {lineNumbers && (
          <div className="select-none text-right pr-3 pl-2 pt-3 pb-3 text-xs font-mono text-[var(--color-text-muted)]/50 bg-[#0d1117] border-r border-[var(--color-border)]/30 leading-[1.5rem] shrink-0">
            {lineNums.map((n) => (
              <div key={n}>{n}</div>
            ))}
          </div>
        )}

        {/* Code textarea */}
        <textarea
          ref={textareaRef}
          value={code}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          placeholder={`Enter ${language} code here...\n\nCtrl+Enter to run`}
          className="flex-1 bg-transparent text-[var(--color-text)] font-mono text-sm p-3 resize-none outline-none leading-[1.5rem] placeholder:text-[var(--color-text-muted)]/40"
          style={{ tabSize: 4 }}
        />
      </div>
    </div>
  );
}
