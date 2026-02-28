"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listModels,
  runBenchmark,
  listBenchmarkResults,
  compareModels,
  createABTest,
  getABTestResults,
  type Model,
  type BenchmarkResult,
  type BenchmarkComparison,
  type ABTest,
  type ABTestResult,
} from "@/lib/models";

const BENCHMARKS = [
  { value: "general_knowledge", label: "General Knowledge (MMLU-style)" },
  { value: "code_generation", label: "Code Generation (HumanEval-style)" },
  { value: "rag_accuracy", label: "RAG Accuracy" },
  { value: "tool_calling", label: "Tool Calling" },
  { value: "instruction_following", label: "Instruction Following" },
];

function ScoreBar({ score, label }: { score: number; label?: string }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8 ? "var(--color-success)" : score >= 0.5 ? "#eab308" : "var(--color-danger)";
  return (
    <div>
      {label && <span className="text-xs text-[var(--color-text-muted)]">{label}</span>}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 rounded-full bg-[var(--color-border)] overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
        </div>
        <span className="text-xs font-medium w-10 text-right">{pct}%</span>
      </div>
    </div>
  );
}

export default function EvaluationPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const [loading, setLoading] = useState(true);

  // Benchmark form
  const [benchModel, setBenchModel] = useState("");
  const [benchType, setBenchType] = useState("general_knowledge");
  const [running, setRunning] = useState(false);

  // Compare form
  const [compareModelA, setCompareModelA] = useState("");
  const [compareModelB, setCompareModelB] = useState("");
  const [compareBench, setCompareBench] = useState("general_knowledge");
  const [comparison, setComparison] = useState<BenchmarkComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  // A/B test
  const [abModelA, setAbModelA] = useState("");
  const [abModelB, setAbModelB] = useState("");
  const [abSplit, setAbSplit] = useState(0.5);
  const [abTests, setAbTests] = useState<ABTest[]>([]);
  const [abResults, setAbResults] = useState<Record<string, ABTestResult>>({});

  const fetchData = async () => {
    try {
      const [modelsRes, resultsRes] = await Promise.all([
        listModels(),
        listBenchmarkResults(),
      ]);
      setModels(modelsRes.models);
      setResults(resultsRes.results);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRunBenchmark = async () => {
    if (!benchModel) return;
    setRunning(true);
    try {
      await runBenchmark({ model_name: benchModel, benchmark: benchType });
      await fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Benchmark failed";
      alert(msg);
    } finally {
      setRunning(false);
    }
  };

  const handleCompare = async () => {
    if (!compareModelA || !compareModelB) return;
    setComparing(true);
    try {
      const res = await compareModels(compareModelA, compareModelB, compareBench);
      setComparison(res);
      await fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Comparison failed";
      alert(msg);
    } finally {
      setComparing(false);
    }
  };

  const handleCreateABTest = async () => {
    if (!abModelA || !abModelB) return;
    try {
      await createABTest(abModelA, abModelB, abSplit);
      alert("A/B test created successfully");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create A/B test";
      alert(msg);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-[var(--color-text-muted)]">Loading...</p>
      </div>
    );
  }

  const modelNames = models.map((m) => m.name);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link href="/models" className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            Models
          </Link>
          <h2 className="text-2xl font-semibold">Evaluation</h2>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Run benchmark */}
        <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">Run Benchmark</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Model</label>
              <select
                value={benchModel}
                onChange={(e) => setBenchModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="">Select model...</option>
                {modelNames.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Benchmark</label>
              <select
                value={benchType}
                onChange={(e) => setBenchType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                {BENCHMARKS.map((b) => (
                  <option key={b.value} value={b.value}>{b.label}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleRunBenchmark}
              disabled={running || !benchModel}
              className="w-full py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {running ? "Running..." : "Run Benchmark"}
            </button>
          </div>
        </div>

        {/* Compare models */}
        <div className="p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">Compare Models</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-[var(--color-text-muted)] mb-1">Model A</label>
                <select
                  value={compareModelA}
                  onChange={(e) => setCompareModelA(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                >
                  <option value="">Select...</option>
                  {modelNames.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-[var(--color-text-muted)] mb-1">Model B</label>
                <select
                  value={compareModelB}
                  onChange={(e) => setCompareModelB(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
                >
                  <option value="">Select...</option>
                  {modelNames.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
            </div>
            <select
              value={compareBench}
              onChange={(e) => setCompareBench(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
            >
              {BENCHMARKS.map((b) => (
                <option key={b.value} value={b.value}>{b.label}</option>
              ))}
            </select>
            <button
              onClick={handleCompare}
              disabled={comparing || !compareModelA || !compareModelB}
              className="w-full py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {comparing ? "Comparing..." : "Compare"}
            </button>

            {comparison && (
              <div className="mt-3 p-3 rounded-lg bg-[var(--color-bg)]">
                <p className="text-sm font-medium mb-2">
                  Winner: <span className="text-[var(--color-primary)]">{comparison.winner}</span>
                </p>
                <ScoreBar score={comparison.score_a} label={comparison.model_a} />
                <div className="mt-1">
                  <ScoreBar score={comparison.score_b} label={comparison.model_b} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Results table */}
        <div className="lg:col-span-2 p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">Benchmark Results</h3>

          {results.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">No benchmark results yet. Run a benchmark above.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="pb-2 pr-4">Model</th>
                    <th className="pb-2 pr-4">Benchmark</th>
                    <th className="pb-2 pr-4">Score</th>
                    <th className="pb-2 pr-4">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.id} className="border-b border-[var(--color-border)]/50">
                      <td className="py-2 pr-4 font-medium">{r.model_name}</td>
                      <td className="py-2 pr-4">
                        {BENCHMARKS.find((b) => b.value === r.benchmark)?.label || r.benchmark}
                      </td>
                      <td className="py-2 pr-4 w-48">
                        <ScoreBar score={r.score} />
                      </td>
                      <td className="py-2 pr-4 text-[var(--color-text-muted)] text-xs">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* A/B Testing */}
        <div className="lg:col-span-2 p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <h3 className="text-lg font-medium mb-4">A/B Testing</h3>
          <div className="grid gap-3 sm:grid-cols-4 items-end">
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Model A</label>
              <select
                value={abModelA}
                onChange={(e) => setAbModelA(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="">Select...</option>
                {modelNames.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">Model B</label>
              <select
                value={abModelB}
                onChange={(e) => setAbModelB(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-sm"
              >
                <option value="">Select...</option>
                {modelNames.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-[var(--color-text-muted)] mb-1">
                Traffic Split ({Math.round(abSplit * 100)}% / {Math.round((1 - abSplit) * 100)}%)
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={abSplit}
                onChange={(e) => setAbSplit(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>
            <button
              onClick={handleCreateABTest}
              disabled={!abModelA || !abModelB}
              className="py-2 rounded-lg bg-[var(--color-primary)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              Create A/B Test
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
