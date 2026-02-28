"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchAgents,
  createAgent,
  deleteAgent,
  fetchTools,
  executeAgent,
  getExecution,
  type Agent,
  type Tool,
  type Execution,
} from "@/lib/agents";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);

  // Create form
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPrompt, setNewPrompt] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);

  // Execution
  const [execPrompt, setExecPrompt] = useState("");
  const [execution, setExecution] = useState<Execution | null>(null);
  const [executing, setExecuting] = useState(false);

  const loadAgents = useCallback(async () => {
    try {
      const data = await fetchAgents();
      setAgents(data.agents);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTools = useCallback(async () => {
    try {
      const data = await fetchTools();
      setTools(data.tools);
    } catch {
      /* empty */
    }
  }, []);

  useEffect(() => {
    loadAgents();
    loadTools();
  }, [loadAgents, loadTools]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAgent({
        name: newName,
        description: newDesc,
        system_prompt: newPrompt,
        tools: selectedTools,
      });
      setNewName("");
      setNewDesc("");
      setNewPrompt("");
      setSelectedTools([]);
      setShowCreate(false);
      loadAgents();
    } catch {
      alert("Failed to create agent");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this agent?")) return;
    try {
      await deleteAgent(id);
      if (selected?.id === id) {
        setSelected(null);
        setExecution(null);
      }
      loadAgents();
    } catch {
      alert("Failed to delete agent");
    }
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !execPrompt.trim()) return;
    setExecuting(true);
    setExecution(null);
    try {
      const exec = await executeAgent(selected.id, execPrompt);
      setExecution(exec);
      // Poll for completion if running
      if (exec.status === "running") {
        const poll = setInterval(async () => {
          try {
            const updated = await getExecution(selected.id, exec.id);
            setExecution(updated);
            if (updated.status !== "running") clearInterval(poll);
          } catch {
            clearInterval(poll);
          }
        }, 2000);
      }
    } catch {
      alert("Execution failed");
    } finally {
      setExecuting(false);
    }
  };

  const toggleTool = (name: string) => {
    setSelectedTools((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    );
  };

  const statusColors: Record<string, string> = {
    running: "bg-blue-500/20 text-blue-400",
    completed: "bg-green-500/20 text-green-400",
    failed: "bg-red-500/20 text-red-400",
    awaiting_approval: "bg-yellow-500/20 text-yellow-400",
  };

  return (
    <div className="flex h-full">
      {/* Left panel: Agent list */}
      <div className="w-72 border-r border-[var(--color-border)] flex flex-col shrink-0">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h2 className="text-lg font-semibold">Agents</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="px-2.5 py-1 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
          >
            + New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <p className="text-sm text-[var(--color-text-muted)] p-3">
              Loading...
            </p>
          ) : agents.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)] p-3">
              No agents yet. Create one to get started.
            </p>
          ) : (
            agents.map((agent) => (
              <div
                key={agent.id}
                onClick={() => {
                  setSelected(agent);
                  setExecution(null);
                }}
                className={`p-3 rounded-md cursor-pointer transition-colors group ${
                  selected?.id === agent.id
                    ? "bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30"
                    : "hover:bg-[var(--color-surface-hover)] border border-transparent"
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-sm font-medium truncate">
                    {agent.name}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(agent.id);
                    }}
                    className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Delete
                  </button>
                </div>
                {agent.description && (
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-1 line-clamp-2">
                    {agent.description}
                  </p>
                )}
                <div className="flex gap-1 mt-1.5 flex-wrap">
                  {agent.tools.slice(0, 3).map((t) => (
                    <span
                      key={t}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
                    >
                      {t}
                    </span>
                  ))}
                  {agent.tools.length > 3 && (
                    <span className="text-[9px] text-[var(--color-text-muted)]">
                      +{agent.tools.length - 3}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {showCreate ? (
          /* Create agent modal */
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              <h3 className="text-lg font-semibold mb-4">Create Agent</h3>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">
                    Name
                  </label>
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    required
                    className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">
                    Description
                  </label>
                  <input
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">
                    System Prompt
                  </label>
                  <textarea
                    value={newPrompt}
                    onChange={(e) => setNewPrompt(e.target.value)}
                    rows={4}
                    className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)] resize-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-text-muted)] mb-2">
                    Tools ({selectedTools.length} selected)
                  </label>
                  <div className="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto p-2 bg-[var(--color-bg)] rounded-md border border-[var(--color-border)]">
                    {tools.map((tool) => (
                      <label
                        key={tool.name}
                        className={`flex items-start gap-2 p-2 rounded cursor-pointer text-xs transition-colors ${
                          selectedTools.includes(tool.name)
                            ? "bg-[var(--color-accent)]/10"
                            : "hover:bg-[var(--color-surface-hover)]"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedTools.includes(tool.name)}
                          onChange={() => toggleTool(tool.name)}
                          className="mt-0.5 accent-[var(--color-accent)]"
                        />
                        <div>
                          <span className="font-medium">{tool.name}</span>
                          <p className="text-[var(--color-text-muted)] line-clamp-1">
                            {tool.description}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
                  >
                    Create Agent
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="px-4 py-2 text-sm border border-[var(--color-border)] rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : !selected ? (
          <div className="flex items-center justify-center h-full text-[var(--color-text-muted)]">
            <p>Select an agent or create a new one</p>
          </div>
        ) : (
          <>
            {/* Agent details */}
            <div className="p-4 border-b border-[var(--color-border)]">
              <h3 className="text-lg font-semibold">{selected.name}</h3>
              {selected.description && (
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  {selected.description}
                </p>
              )}
              <div className="flex gap-1.5 mt-2 flex-wrap">
                {selected.tools.map((t) => (
                  <span
                    key={t}
                    className="text-[10px] px-2 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
                  >
                    {t}
                  </span>
                ))}
              </div>
              {selected.system_prompt && (
                <details className="mt-2">
                  <summary className="text-xs text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)]">
                    System prompt
                  </summary>
                  <pre className="mt-1 text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] p-2 rounded-md whitespace-pre-wrap">
                    {selected.system_prompt}
                  </pre>
                </details>
              )}
            </div>

            {/* Execute form */}
            <form
              onSubmit={handleExecute}
              className="p-4 border-b border-[var(--color-border)] flex gap-2"
            >
              <input
                value={execPrompt}
                onChange={(e) => setExecPrompt(e.target.value)}
                placeholder="Enter a prompt to execute..."
                className="flex-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-accent)]"
              />
              <button
                type="submit"
                disabled={executing}
                className="px-4 py-2 text-sm bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50 text-white rounded-md transition-colors"
              >
                {executing ? "Running..." : "Execute"}
              </button>
            </form>

            {/* Execution viewer */}
            <div className="flex-1 overflow-y-auto p-4">
              {execution ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${statusColors[execution.status] || "bg-gray-500/20 text-gray-400"}`}
                    >
                      {execution.status}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {execution.steps.length} step
                      {execution.steps.length !== 1 ? "s" : ""}
                    </span>
                  </div>

                  {execution.steps.map((step) => (
                    <div
                      key={step.step_number}
                      className="p-3 bg-[var(--color-surface)] rounded-md border border-[var(--color-border)]"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium">
                          Step {step.step_number}
                          {step.tool_name && (
                            <span className="ml-2 text-[var(--color-accent)]">
                              {step.tool_name}
                            </span>
                          )}
                        </span>
                        {step.duration_ms != null && (
                          <span className="text-[10px] text-[var(--color-text-muted)]">
                            {step.duration_ms}ms
                          </span>
                        )}
                      </div>
                      {step.reasoning && (
                        <p className="text-xs text-[var(--color-text-muted)] mb-1">
                          {step.reasoning}
                        </p>
                      )}
                      {step.tool_input && (
                        <pre className="text-[10px] bg-[var(--color-bg)] p-2 rounded mt-1 overflow-x-auto">
                          {JSON.stringify(step.tool_input, null, 2)}
                        </pre>
                      )}
                      {step.tool_output && (
                        <pre className="text-[10px] bg-[var(--color-bg)] p-2 rounded mt-1 overflow-x-auto text-green-400">
                          {step.tool_output}
                        </pre>
                      )}
                    </div>
                  ))}

                  {execution.result && (
                    <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-md">
                      <p className="text-xs font-medium text-green-400 mb-1">
                        Result
                      </p>
                      <p className="text-sm whitespace-pre-wrap">
                        {execution.result}
                      </p>
                    </div>
                  )}

                  {execution.error && (
                    <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-md">
                      <p className="text-xs font-medium text-red-400 mb-1">
                        Error
                      </p>
                      <p className="text-sm text-red-400">
                        {execution.error}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                  Enter a prompt above and click Execute to run the agent.
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
