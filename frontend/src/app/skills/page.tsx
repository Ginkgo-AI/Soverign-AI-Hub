"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

interface SkillCatalog {
  id: string;
  name: string;
  description: string;
  category: string;
  catalog_summary: string;
  icon: string;
  version: string;
  enabled: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  research: "bg-blue-500/20 text-blue-400",
  analysis: "bg-purple-500/20 text-purple-400",
  coding: "bg-green-500/20 text-green-400",
  writing: "bg-amber-500/20 text-amber-400",
  operations: "bg-red-500/20 text-red-400",
};

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillCatalog[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      const url = selectedCategory
        ? `/api/skills?category=${selectedCategory}`
        : "/api/skills";
      const data = await apiJson<{ skills: SkillCatalog[] }>(url);
      setSkills(data.skills);
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [selectedCategory]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const categories = [...new Set(skills.map((s) => s.category))];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Skills</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Packaged capabilities that enhance your AI agents
        </p>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            selectedCategory === null
              ? "bg-[var(--color-accent)] text-white"
              : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          }`}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
              selectedCategory === cat
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">Loading skills...</p>
      ) : skills.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)]">No skills available. Skills will be seeded on first use.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="p-4 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)]/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium text-sm">{skill.name}</h3>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded capitalize ${
                    CATEGORY_COLORS[skill.category] || "bg-gray-500/20 text-gray-400"
                  }`}
                >
                  {skill.category}
                </span>
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mb-3">
                {skill.catalog_summary || skill.description}
              </p>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[var(--color-text-muted)]">v{skill.version}</span>
                <button className="px-3 py-1 rounded text-xs bg-[var(--color-accent)]/20 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/30">
                  Activate
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
