"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkflowNode {
  id: string;
  type: "agent" | "input" | "output" | "condition";
  label: string;
  x: number;
  y: number;
  config: Record<string, string>;
}

interface WorkflowEdge {
  id: string;
  from: string;
  to: string;
}

interface WorkflowTemplate {
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

const templates: WorkflowTemplate[] = [
  {
    name: "RAG Pipeline",
    description: "Document retrieval → LLM generation with context",
    nodes: [
      { id: "n1", type: "input", label: "User Query", x: 80, y: 180, config: {} },
      { id: "n2", type: "agent", label: "Retriever", x: 320, y: 120, config: { tool: "search_documents" } },
      { id: "n3", type: "agent", label: "Generator", x: 560, y: 180, config: { tool: "chat_completion" } },
      { id: "n4", type: "output", label: "Response", x: 800, y: 180, config: {} },
    ],
    edges: [
      { id: "e1", from: "n1", to: "n2" },
      { id: "e2", from: "n2", to: "n3" },
      { id: "e3", from: "n1", to: "n3" },
      { id: "e4", from: "n3", to: "n4" },
    ],
  },
  {
    name: "Code Review",
    description: "Analyze code → Check style → Generate review",
    nodes: [
      { id: "n1", type: "input", label: "Code Input", x: 80, y: 180, config: {} },
      { id: "n2", type: "agent", label: "Analyzer", x: 320, y: 100, config: { tool: "analyze_code" } },
      { id: "n3", type: "agent", label: "Style Check", x: 320, y: 260, config: { tool: "lint_code" } },
      { id: "n4", type: "agent", label: "Reviewer", x: 560, y: 180, config: { tool: "review_code" } },
      { id: "n5", type: "output", label: "Review", x: 800, y: 180, config: {} },
    ],
    edges: [
      { id: "e1", from: "n1", to: "n2" },
      { id: "e2", from: "n1", to: "n3" },
      { id: "e3", from: "n2", to: "n4" },
      { id: "e4", from: "n3", to: "n4" },
      { id: "e5", from: "n4", to: "n5" },
    ],
  },
  {
    name: "Document Analysis",
    description: "Upload → Extract → Summarize → Classify",
    nodes: [
      { id: "n1", type: "input", label: "Document", x: 80, y: 180, config: {} },
      { id: "n2", type: "agent", label: "Extractor", x: 300, y: 180, config: { tool: "extract_text" } },
      { id: "n3", type: "agent", label: "Summarizer", x: 520, y: 120, config: { tool: "summarize" } },
      { id: "n4", type: "agent", label: "Classifier", x: 520, y: 240, config: { tool: "classify" } },
      { id: "n5", type: "output", label: "Results", x: 760, y: 180, config: {} },
    ],
    edges: [
      { id: "e1", from: "n1", to: "n2" },
      { id: "e2", from: "n2", to: "n3" },
      { id: "e3", from: "n2", to: "n4" },
      { id: "e4", from: "n3", to: "n5" },
      { id: "e5", from: "n4", to: "n5" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Node palette items for drag creation
// ---------------------------------------------------------------------------

const nodeTypes = [
  { type: "input" as const, label: "Input", color: "var(--color-accent)" },
  { type: "agent" as const, label: "Agent", color: "var(--color-warning)" },
  { type: "condition" as const, label: "Condition", color: "var(--color-success)" },
  { type: "output" as const, label: "Output", color: "var(--color-danger)" },
];

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

let nextId = 100;

export default function WorkflowsPage() {
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ id: string; offsetX: number; offsetY: number } | null>(null);
  const [workflowName, setWorkflowName] = useState("Untitled Workflow");
  const canvasRef = useRef<HTMLDivElement>(null);

  const addNode = useCallback(
    (type: WorkflowNode["type"], x: number, y: number) => {
      const id = `n${nextId++}`;
      const labels: Record<string, string> = {
        input: "Input",
        agent: "Agent",
        condition: "Condition",
        output: "Output",
      };
      setNodes((prev) => [
        ...prev,
        { id, type, label: labels[type], x, y, config: {} },
      ]);
    },
    []
  );

  const removeNode = (id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.from !== id && e.to !== id));
    if (selectedNode === id) setSelectedNode(null);
  };

  const addEdge = (from: string, to: string) => {
    if (from === to) return;
    if (edges.some((e) => e.from === from && e.to === to)) return;
    const id = `e${nextId++}`;
    setEdges((prev) => [...prev, { id, from, to }]);
  };

  const removeEdge = (id: string) => {
    setEdges((prev) => prev.filter((e) => e.id !== id));
  };

  const loadTemplate = (tmpl: WorkflowTemplate) => {
    setNodes(tmpl.nodes.map((n) => ({ ...n })));
    setEdges(tmpl.edges.map((e) => ({ ...e })));
    setWorkflowName(tmpl.name);
    setSelectedNode(null);
  };

  const handleCanvasMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragging || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - dragging.offsetX;
      const y = e.clientY - rect.top - dragging.offsetY;
      setNodes((prev) =>
        prev.map((n) =>
          n.id === dragging.id ? { ...n, x: Math.max(0, x), y: Math.max(0, y) } : n
        )
      );
    },
    [dragging]
  );

  const handleCanvasMouseUp = useCallback(() => {
    setDragging(null);
  }, []);

  // Add listener for mouse up anywhere
  useEffect(() => {
    const handler = () => setDragging(null);
    window.addEventListener("mouseup", handler);
    return () => window.removeEventListener("mouseup", handler);
  }, []);

  const nodeColors: Record<string, string> = {
    input: "border-[var(--color-accent)]",
    agent: "border-[var(--color-warning)]",
    condition: "border-[var(--color-success)]",
    output: "border-[var(--color-danger)]",
  };

  const nodeHeaderColors: Record<string, string> = {
    input: "bg-[var(--color-accent)]/20 text-[var(--color-accent)]",
    agent: "bg-[var(--color-warning)]/20 text-[var(--color-warning)]",
    condition: "bg-[var(--color-success)]/20 text-[var(--color-success)]",
    output: "bg-[var(--color-danger)]/20 text-[var(--color-danger)]",
  };

  const getNodeCenter = (node: WorkflowNode) => ({
    x: node.x + 70,
    y: node.y + 30,
  });

  return (
    <div className="flex h-full">
      {/* Left panel: Palette + Templates */}
      <div className="w-64 border-r border-[var(--color-border)] flex flex-col shrink-0">
        <div className="p-4 border-b border-[var(--color-border)]">
          <h2 className="text-lg font-semibold">Workflows</h2>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
            Visual workflow builder
          </p>
        </div>

        {/* Node palette */}
        <div className="p-3 border-b border-[var(--color-border)]">
          <p className="text-xs text-[var(--color-text-muted)] mb-2">
            Click to add node
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {nodeTypes.map((nt) => (
              <button
                key={nt.type}
                onClick={() => addNode(nt.type, 200 + Math.random() * 200, 100 + Math.random() * 200)}
                className="p-2 text-xs rounded-md border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-center"
                style={{ borderLeftColor: nt.color, borderLeftWidth: 3 }}
              >
                {nt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Templates */}
        <div className="p-3 border-b border-[var(--color-border)]">
          <p className="text-xs text-[var(--color-text-muted)] mb-2">
            Templates
          </p>
          <div className="space-y-1.5">
            {templates.map((tmpl) => (
              <button
                key={tmpl.name}
                onClick={() => loadTemplate(tmpl)}
                className="w-full text-left p-2 rounded-md hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <span className="text-xs font-medium">{tmpl.name}</span>
                <p className="text-[10px] text-[var(--color-text-muted)]">
                  {tmpl.description}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Node properties */}
        {selectedNode && (
          <div className="p-3 flex-1 overflow-y-auto">
            <p className="text-xs text-[var(--color-text-muted)] mb-2">
              Properties
            </p>
            {(() => {
              const node = nodes.find((n) => n.id === selectedNode);
              if (!node) return null;
              return (
                <div className="space-y-2">
                  <div>
                    <label className="block text-[10px] text-[var(--color-text-muted)] mb-0.5">
                      Label
                    </label>
                    <input
                      value={node.label}
                      onChange={(e) =>
                        setNodes((prev) =>
                          prev.map((n) =>
                            n.id === node.id
                              ? { ...n, label: e.target.value }
                              : n
                          )
                        )
                      }
                      className="w-full bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-2 py-1.5 text-xs focus:outline-none focus:border-[var(--color-accent)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-[var(--color-text-muted)] mb-0.5">
                      Type
                    </label>
                    <p className="text-xs capitalize">{node.type}</p>
                  </div>
                  <button
                    onClick={() => removeNode(node.id)}
                    className="w-full mt-2 py-1.5 text-xs border border-[var(--color-danger)]/30 text-[var(--color-danger)] rounded hover:bg-[var(--color-danger)]/10 transition-colors"
                  >
                    Delete Node
                  </button>
                </div>
              );
            })()}
          </div>
        )}

        {/* Workflow actions */}
        <div className="p-3 border-t border-[var(--color-border)]">
          <div className="flex gap-2">
            <button
              onClick={() => {
                setNodes([]);
                setEdges([]);
                setSelectedNode(null);
                setWorkflowName("Untitled Workflow");
              }}
              className="flex-1 py-1.5 text-xs border border-[var(--color-border)] rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              Clear
            </button>
            <button
              onClick={() => {
                const data = JSON.stringify({ name: workflowName, nodes, edges }, null, 2);
                const blob = new Blob([data], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${workflowName.toLowerCase().replace(/\s+/g, "-")}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex-1 py-1.5 text-xs bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-md transition-colors"
            >
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-3 border-b border-[var(--color-border)] flex items-center gap-3">
          <input
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            className="bg-transparent text-sm font-semibold focus:outline-none border-b border-transparent focus:border-[var(--color-accent)]"
          />
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {nodes.length} nodes &middot; {edges.length} edges
          </span>
          {connecting && (
            <span className="text-[10px] text-[var(--color-accent)]">
              Click a target node to connect...
              <button
                onClick={() => setConnecting(null)}
                className="ml-2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                Cancel
              </button>
            </span>
          )}
        </div>

        <div
          ref={canvasRef}
          className="flex-1 relative overflow-auto bg-[var(--color-bg)]"
          style={{
            backgroundImage:
              "radial-gradient(circle, var(--color-border) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
        >
          {/* Edges (SVG) */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {edges.map((edge) => {
              const fromNode = nodes.find((n) => n.id === edge.from);
              const toNode = nodes.find((n) => n.id === edge.to);
              if (!fromNode || !toNode) return null;
              const from = getNodeCenter(fromNode);
              const to = getNodeCenter(toNode);
              const midX = (from.x + to.x) / 2;
              return (
                <g key={edge.id} className="pointer-events-auto">
                  <path
                    d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
                    fill="none"
                    stroke="var(--color-border)"
                    strokeWidth="2"
                  />
                  <path
                    d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="12"
                    className="cursor-pointer"
                    onClick={() => removeEdge(edge.id)}
                  />
                  {/* Arrow */}
                  <circle cx={to.x} cy={to.y} r="3" fill="var(--color-border)" />
                </g>
              );
            })}
          </svg>

          {/* Nodes */}
          {nodes.map((node) => (
            <div
              key={node.id}
              className={`absolute select-none rounded-lg border-2 bg-[var(--color-surface)] shadow-lg cursor-grab active:cursor-grabbing ${nodeColors[node.type]} ${
                selectedNode === node.id ? "ring-2 ring-[var(--color-accent)]" : ""
              }`}
              style={{
                left: node.x,
                top: node.y,
                minWidth: 140,
              }}
              onMouseDown={(e) => {
                if (connecting) {
                  addEdge(connecting, node.id);
                  setConnecting(null);
                  return;
                }
                setSelectedNode(node.id);
                const rect = (e.target as HTMLElement).closest(".absolute")!.getBoundingClientRect();
                setDragging({
                  id: node.id,
                  offsetX: e.clientX - rect.left,
                  offsetY: e.clientY - rect.top,
                });
              }}
            >
              <div
                className={`px-3 py-1 text-[10px] font-medium uppercase tracking-wider rounded-t-md ${nodeHeaderColors[node.type]}`}
              >
                {node.type}
              </div>
              <div className="px-3 py-2 text-xs font-medium">{node.label}</div>
              <div className="px-3 pb-2 flex justify-end">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setConnecting(node.id);
                  }}
                  className="text-[9px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
                >
                  Connect &rarr;
                </button>
              </div>
            </div>
          ))}

          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-[var(--color-text-muted)]">
                <p className="text-sm">
                  Add nodes from the palette or load a template
                </p>
                <p className="text-[10px] mt-1">
                  Click a node, then &quot;Connect&quot; to create edges
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
