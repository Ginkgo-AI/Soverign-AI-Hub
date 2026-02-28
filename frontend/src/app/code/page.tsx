"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { CodeEditor } from "@/components/code/CodeEditor";
import { OutputPanel } from "@/components/code/OutputPanel";
import { FileTree } from "@/components/code/FileTree";
import {
  executeCode,
  listWorkspaces,
  createWorkspace,
  getWorkspace,
  readFile,
  writeFile,
  deleteFile as deleteFileApi,
  analyzeCode,
  explainCode,
  generateCode,
  reviewCode,
  type Workspace,
  type FileTreeNode,
  type ExecuteResult,
  type AnalyzeResult,
} from "@/lib/code";

type RightPanel = "output" | "chat" | "analysis";

export default function CodePage() {
  const { loadFromStorage, isAuthenticated } = useAuthStore();

  // Editor state
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Output state
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [returnValue, setReturnValue] = useState<string | null>(null);
  const [executionTimeMs, setExecutionTimeMs] = useState(0);
  const [exitCode, setExitCode] = useState(0);

  // Workspace state
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [fileTree, setFileTree] = useState<FileTreeNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);

  // Right panel state
  const [rightPanel, setRightPanel] = useState<RightPanel>("output");
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResult | null>(null);
  const [chatResponse, setChatResponse] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");

  // New workspace dialog
  const [showNewWs, setShowNewWs] = useState(false);
  const [newWsName, setNewWsName] = useState("");

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  useEffect(() => {
    if (isAuthenticated) {
      loadWorkspaces();
    }
  }, [isAuthenticated]);

  const loadWorkspaces = useCallback(async () => {
    try {
      const result = await listWorkspaces();
      setWorkspaces(result.workspaces);
    } catch {
      // Workspaces may not be available
    }
  }, []);

  const handleSelectWorkspace = useCallback(async (ws: Workspace) => {
    try {
      const full = await getWorkspace(ws.id);
      setActiveWorkspace(full);
      setFileTree(full.file_tree || []);
      setSelectedFile(null);
    } catch (err) {
      console.error("Failed to load workspace", err);
    }
  }, []);

  const handleCreateWorkspace = useCallback(async () => {
    if (!newWsName.trim()) return;
    try {
      const ws = await createWorkspace(newWsName.trim());
      setWorkspaces((prev) => [ws, ...prev]);
      setShowNewWs(false);
      setNewWsName("");
      await handleSelectWorkspace(ws);
    } catch (err) {
      console.error("Failed to create workspace", err);
    }
  }, [newWsName, handleSelectWorkspace]);

  const handleFileSelect = useCallback(
    async (path: string) => {
      if (!activeWorkspace) return;
      try {
        const file = await readFile(activeWorkspace.id, path);
        setCode(file.content);
        setSelectedFile(path);
        if (file.language) {
          const langMap: Record<string, string> = {
            python: "python",
            javascript: "javascript",
            typescript: "javascript",
            bash: "bash",
            sql: "sql",
          };
          if (langMap[file.language]) {
            setLanguage(langMap[file.language]);
          }
        }
      } catch (err) {
        console.error("Failed to read file", err);
      }
    },
    [activeWorkspace]
  );

  const handleSaveFile = useCallback(async () => {
    if (!activeWorkspace || !selectedFile) return;
    try {
      await writeFile(activeWorkspace.id, selectedFile, code);
    } catch (err) {
      console.error("Failed to save file", err);
    }
  }, [activeWorkspace, selectedFile, code]);

  const handleDeleteFile = useCallback(
    async (path: string) => {
      if (!activeWorkspace) return;
      if (!confirm(`Delete ${path}?`)) return;
      try {
        await deleteFileApi(activeWorkspace.id, path);
        if (selectedFile === path) {
          setSelectedFile(null);
          setCode("");
        }
        // Refresh file tree
        const full = await getWorkspace(activeWorkspace.id);
        setFileTree(full.file_tree || []);
      } catch (err) {
        console.error("Failed to delete file", err);
      }
    },
    [activeWorkspace, selectedFile]
  );

  const handleRun = useCallback(async () => {
    if (!code.trim() || isRunning) return;
    setIsRunning(true);
    setRightPanel("output");

    try {
      const result: ExecuteResult = await executeCode(
        code,
        language,
        sessionId || undefined
      );
      setStdout(result.stdout);
      setStderr(result.stderr);
      setReturnValue(result.return_value);
      setExecutionTimeMs(result.execution_time_ms);
      setExitCode(result.exit_code);
      if (result.session_id) {
        setSessionId(result.session_id);
      }
    } catch (err) {
      setStderr(err instanceof Error ? err.message : "Execution failed");
      setExitCode(1);
    } finally {
      setIsRunning(false);
    }
  }, [code, language, isRunning, sessionId]);

  const handleClearOutput = useCallback(() => {
    setStdout("");
    setStderr("");
    setReturnValue(null);
    setExecutionTimeMs(0);
    setExitCode(0);
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!code.trim()) return;
    setRightPanel("analysis");
    try {
      const result = await analyzeCode(code, language);
      setAnalysisResult(result);
    } catch (err) {
      setAnalysisResult(null);
    }
  }, [code, language]);

  const handleChatSubmit = useCallback(async () => {
    if (!chatInput.trim() || chatLoading) return;
    setChatLoading(true);
    setRightPanel("chat");

    try {
      // Determine what action to take based on input
      const input = chatInput.toLowerCase();
      if (input.includes("explain")) {
        const result = await explainCode(code, language);
        setChatResponse(result.explanation);
      } else if (input.includes("generate") || input.includes("write")) {
        const result = await generateCode(chatInput, language, code || undefined);
        setChatResponse(
          result.code
            ? `\`\`\`${language}\n${result.code}\n\`\`\`\n\n${result.explanation}`
            : result.explanation
        );
      } else if (input.includes("review") || input.includes("bug")) {
        const result = await reviewCode(code, undefined, language);
        setChatResponse(result.summary);
      } else {
        // Default: explain the code with the question as context
        const result = await explainCode(code, language, "detailed");
        setChatResponse(result.explanation);
      }
    } catch (err) {
      setChatResponse(
        err instanceof Error ? `Error: ${err.message}` : "Request failed"
      );
    } finally {
      setChatLoading(false);
      setChatInput("");
    }
  }, [chatInput, chatLoading, code, language]);

  return (
    <div className="flex h-full">
      {/* File tree sidebar */}
      {showSidebar && (
        <div className="w-56 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col shrink-0">
          {/* Workspace selector */}
          <div className="p-2 border-b border-[var(--color-border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[var(--color-text-muted)]">
                Workspace
              </span>
              <button
                onClick={() => setShowNewWs(true)}
                className="text-xs text-[var(--color-accent)] hover:opacity-80"
                title="New workspace"
              >
                + New
              </button>
            </div>

            {showNewWs && (
              <div className="flex gap-1 mb-2">
                <input
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateWorkspace()}
                  placeholder="Name..."
                  className="flex-1 px-2 py-1 text-xs rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)]"
                  autoFocus
                />
                <button
                  onClick={handleCreateWorkspace}
                  className="px-2 py-1 text-xs rounded bg-[var(--color-accent)] text-white"
                >
                  OK
                </button>
                <button
                  onClick={() => {
                    setShowNewWs(false);
                    setNewWsName("");
                  }}
                  className="px-1 text-xs text-[var(--color-text-muted)]"
                >
                  x
                </button>
              </div>
            )}

            <select
              value={activeWorkspace?.id || ""}
              onChange={(e) => {
                const ws = workspaces.find((w) => w.id === e.target.value);
                if (ws) handleSelectWorkspace(ws);
              }}
              className="w-full px-2 py-1 text-xs rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)]"
            >
              <option value="">Select workspace...</option>
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          </div>

          {/* File tree */}
          <div className="flex-1 overflow-hidden">
            <FileTree
              nodes={fileTree}
              onFileSelect={handleFileSelect}
              selectedPath={selectedFile}
              onDeleteFile={handleDeleteFile}
            />
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              title={showSidebar ? "Hide sidebar" : "Show sidebar"}
            >
              {showSidebar ? "\u25C0" : "\u25B6"} Files
            </button>
            <h2 className="text-sm font-medium">Code Assistant</h2>
            {selectedFile && (
              <span className="text-xs text-[var(--color-text-muted)]">
                {selectedFile}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selectedFile && (
              <button
                onClick={handleSaveFile}
                className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                Save
              </button>
            )}
            <button
              onClick={handleAnalyze}
              disabled={!code.trim()}
              className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
            >
              Analyze
            </button>
            <a
              href="/code/notebook"
              className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            >
              Notebook
            </a>
          </div>
        </div>

        {/* Split panes: editor on left, output/chat on right */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Code Editor */}
          <div className="flex-1 p-2 min-w-0">
            <CodeEditor
              code={code}
              onChange={setCode}
              language={language}
              onLanguageChange={setLanguage}
              onRun={handleRun}
              onClear={() => setCode("")}
              isRunning={isRunning}
            />
          </div>

          {/* Right: Output / Chat / Analysis */}
          <div className="w-[420px] flex flex-col border-l border-[var(--color-border)] shrink-0">
            {/* Panel tabs */}
            <div className="flex border-b border-[var(--color-border)] bg-[var(--color-surface)]">
              {(
                [
                  { key: "output", label: "Output" },
                  { key: "chat", label: "AI Chat" },
                  { key: "analysis", label: "Analysis" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setRightPanel(tab.key)}
                  className={`flex-1 py-2 text-xs transition-colors relative ${
                    rightPanel === tab.key
                      ? "text-[var(--color-text)]"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  {tab.label}
                  {rightPanel === tab.key && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)]" />
                  )}
                </button>
              ))}
            </div>

            {/* Panel content */}
            <div className="flex-1 overflow-hidden">
              {rightPanel === "output" && (
                <div className="h-full p-2">
                  <OutputPanel
                    stdout={stdout}
                    stderr={stderr}
                    returnValue={returnValue}
                    executionTimeMs={executionTimeMs}
                    exitCode={exitCode}
                    onClear={handleClearOutput}
                  />
                </div>
              )}

              {rightPanel === "chat" && (
                <div className="flex flex-col h-full">
                  <div className="flex-1 overflow-y-auto p-3">
                    {chatResponse ? (
                      <div className="text-xs leading-relaxed text-[var(--color-text)] whitespace-pre-wrap">
                        {chatResponse}
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Ask about your code: explain, review, generate...
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="border-t border-[var(--color-border)] p-2">
                    <div className="flex gap-2">
                      <input
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) =>
                          e.key === "Enter" && handleChatSubmit()
                        }
                        placeholder="Ask about this code..."
                        disabled={chatLoading}
                        className="flex-1 px-3 py-2 text-xs rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] disabled:opacity-50"
                      />
                      <button
                        onClick={handleChatSubmit}
                        disabled={chatLoading || !chatInput.trim()}
                        className="px-3 py-2 text-xs rounded bg-[var(--color-accent)] text-white disabled:opacity-50"
                      >
                        {chatLoading ? "..." : "Send"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {rightPanel === "analysis" && (
                <div className="h-full overflow-y-auto p-3">
                  {analysisResult ? (
                    <div className="space-y-3">
                      <div className="text-xs text-[var(--color-text-muted)]">
                        {analysisResult.summary}
                      </div>
                      {analysisResult.issues.map((issue, i) => (
                        <div
                          key={i}
                          className={`p-2 rounded text-xs border ${
                            issue.severity === "error"
                              ? "border-red-500/30 bg-red-950/20"
                              : issue.severity === "warning"
                                ? "border-yellow-500/30 bg-yellow-950/20"
                                : "border-blue-500/30 bg-blue-950/20"
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={`font-semibold ${
                                issue.severity === "error"
                                  ? "text-red-400"
                                  : issue.severity === "warning"
                                    ? "text-yellow-400"
                                    : "text-blue-400"
                              }`}
                            >
                              {issue.severity.toUpperCase()}
                            </span>
                            {issue.line && (
                              <span className="text-[var(--color-text-muted)]">
                                Line {issue.line}
                              </span>
                            )}
                            {issue.rule && (
                              <span className="text-[var(--color-text-muted)]/60">
                                [{issue.rule}]
                              </span>
                            )}
                          </div>
                          <p className="text-[var(--color-text)]">
                            {issue.message}
                          </p>
                        </div>
                      ))}
                      {analysisResult.issues.length === 0 && (
                        <p className="text-xs text-green-400">
                          No issues found.
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <p className="text-xs text-[var(--color-text-muted)]">
                        Click &quot;Analyze&quot; to check your code
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
