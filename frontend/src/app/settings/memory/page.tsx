"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface UserMemoryItem {
  id: string;
  memory_type: string;
  key: string;
  value: string;
  confidence: number;
  created_at: string;
  updated_at: string;
}

interface KnowledgeItem {
  id: string;
  subject: string;
  predicate: string;
  object_value: string;
  confidence: number;
  created_at: string;
}

type Tab = "preferences" | "knowledge" | "summaries";

export default function MemorySettingsPage() {
  const [tab, setTab] = useState<Tab>("preferences");
  const [memories, setMemories] = useState<UserMemoryItem[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "preferences") {
        const data = await apiJson<{ memories: UserMemoryItem[] }>("/api/memory?memory_type=preference");
        setMemories(data.memories);
      } else if (tab === "knowledge") {
        const data = await apiJson<{ entries: KnowledgeItem[] }>("/api/memory/knowledge");
        setKnowledge(data.entries);
      }
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const deleteMemory = async (id: string) => {
    await apiJson(`/api/memory/${id}`, { method: "DELETE" });
    fetchData();
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Memory</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Manage what the AI remembers about you across conversations
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[var(--color-surface)] rounded-lg p-1 w-fit">
        {(["preferences", "knowledge", "summaries"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "bg-[var(--color-accent)] text-white"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">Loading...</p>
      ) : tab === "preferences" ? (
        <div className="space-y-2">
          {memories.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">
              No memories yet. Chat with the AI and it will automatically remember your preferences.
            </p>
          ) : (
            memories.map((m) => (
              <div key={m.id} className="flex items-center justify-between p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{m.key}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-border)] text-[var(--color-text-muted)]">
                      {m.memory_type}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">{m.value}</p>
                </div>
                <button
                  onClick={() => deleteMemory(m.id)}
                  className="px-3 py-1 rounded text-xs text-red-400 hover:bg-red-500/20"
                >
                  Forget
                </button>
              </div>
            ))
          )}
        </div>
      ) : tab === "knowledge" ? (
        <div className="space-y-2">
          {knowledge.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">
              No knowledge entries yet. These are automatically extracted from your conversations.
            </p>
          ) : (
            knowledge.map((k) => (
              <div key={k.id} className="p-3 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)]">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-[var(--color-accent)]">{k.subject}</span>
                  <span className="text-[var(--color-text-muted)]">{k.predicate}</span>
                  <span>{k.object_value}</span>
                </div>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                  Confidence: {Math.round(k.confidence * 100)}%
                </p>
              </div>
            ))
          )}
        </div>
      ) : (
        <p className="text-sm text-[var(--color-text-muted)]">
          Conversation summaries are generated automatically. Check back after a few conversations.
        </p>
      )}
    </div>
  );
}
