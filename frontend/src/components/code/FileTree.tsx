"use client";

import { useState, useCallback } from "react";
import type { FileTreeNode } from "@/lib/code";

interface FileTreeProps {
  nodes: FileTreeNode[];
  onFileSelect: (path: string) => void;
  selectedPath: string | null;
  onCreateFile?: (parentPath: string) => void;
  onDeleteFile?: (path: string) => void;
}

const FILE_ICONS: Record<string, string> = {
  python: "PY",
  javascript: "JS",
  typescript: "TS",
  html: "HT",
  css: "CS",
  json: "JN",
  markdown: "MD",
  bash: "SH",
  sql: "SQ",
  yaml: "YM",
  rust: "RS",
  go: "GO",
  java: "JA",
  cpp: "C+",
  c: "C",
};

function getFileIcon(node: FileTreeNode): string {
  if (node.is_dir) return "\u{1F4C1}";
  return FILE_ICONS[node.language || ""] || "\u{1F4C4}";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function TreeNode({
  node,
  depth,
  onFileSelect,
  selectedPath,
  onDeleteFile,
}: {
  node: FileTreeNode;
  depth: number;
  onFileSelect: (path: string) => void;
  selectedPath: string | null;
  onDeleteFile?: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isSelected = selectedPath === node.path;

  const handleClick = useCallback(() => {
    if (node.is_dir) {
      setExpanded((prev) => !prev);
    } else {
      onFileSelect(node.path);
    }
  }, [node, onFileSelect]);

  return (
    <div>
      <div
        onClick={handleClick}
        className={`flex items-center gap-1.5 px-2 py-1 text-xs cursor-pointer rounded transition-colors group ${
          isSelected
            ? "bg-[var(--color-accent)]/20 text-[var(--color-accent)]"
            : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {/* Expand/collapse indicator for dirs */}
        {node.is_dir && (
          <span className="w-3 text-center text-[10px]">
            {expanded ? "\u25BC" : "\u25B6"}
          </span>
        )}

        {/* Icon */}
        <span className="w-5 text-center text-[10px] font-mono shrink-0">
          {node.is_dir ? (expanded ? "\u{1F4C2}" : "\u{1F4C1}") : ""}
          {!node.is_dir && (
            <span
              className={`inline-block px-0.5 rounded text-[8px] font-bold ${
                node.language === "python"
                  ? "text-blue-400"
                  : node.language === "javascript" || node.language === "typescript"
                    ? "text-yellow-400"
                    : node.language === "bash"
                      ? "text-green-400"
                      : "text-[var(--color-text-muted)]"
              }`}
            >
              {FILE_ICONS[node.language || ""] || "\u00B7"}
            </span>
          )}
        </span>

        {/* Name */}
        <span className="truncate flex-1">{node.name}</span>

        {/* Size for files */}
        {!node.is_dir && node.size > 0 && (
          <span className="text-[10px] text-[var(--color-text-muted)]/60 shrink-0">
            {formatSize(node.size)}
          </span>
        )}

        {/* Delete button (hidden until hover) */}
        {onDeleteFile && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDeleteFile(node.path);
            }}
            className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 text-[10px] px-1 transition-opacity"
            title="Delete"
          >
            x
          </button>
        )}
      </div>

      {/* Children */}
      {node.is_dir && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onFileSelect={onFileSelect}
              selectedPath={selectedPath}
              onDeleteFile={onDeleteFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({
  nodes,
  onFileSelect,
  selectedPath,
  onCreateFile,
  onDeleteFile,
}: FileTreeProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)]">
        <span className="text-xs font-medium text-[var(--color-text-muted)]">
          Files
        </span>
        {onCreateFile && (
          <button
            onClick={() => onCreateFile("")}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            title="New file"
          >
            +
          </button>
        )}
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1">
        {nodes.length === 0 ? (
          <div className="px-3 py-4 text-center">
            <p className="text-xs text-[var(--color-text-muted)]">
              No files yet
            </p>
          </div>
        ) : (
          nodes.map((node) => (
            <TreeNode
              key={node.path}
              node={node}
              depth={0}
              onFileSelect={onFileSelect}
              selectedPath={selectedPath}
              onDeleteFile={onDeleteFile}
            />
          ))
        )}
      </div>
    </div>
  );
}
