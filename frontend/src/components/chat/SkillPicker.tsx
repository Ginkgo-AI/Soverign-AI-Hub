"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "@/lib/api";
import { useChatStore } from "@/stores/chatStore";

interface SkillOption {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
}

export function SkillPicker() {
  const { activeSkillId, setActiveSkillId } = useChatStore();
  const [skills, setSkills] = useState<SkillOption[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await apiJson<{ skills: SkillOption[] }>("/api/skills");
        setSkills(data.skills);
      } catch {
        // Skills not available
      }
    };
    fetch();
  }, []);

  const activeName = skills.find((s) => s.id === activeSkillId)?.name;

  if (skills.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)]/50 transition-colors"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 3l1.5 5.5H19l-4.5 3.5 1.5 5.5L12 14l-4 3.5 1.5-5.5L5 8.5h5.5z" />
        </svg>
        {activeName || "No Skill"}
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-64 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg z-50 overflow-hidden">
          <button
            onClick={() => { setActiveSkillId(null); setOpen(false); }}
            className={`w-full text-left px-3 py-2 text-xs hover:bg-[var(--color-surface-hover)] ${
              !activeSkillId ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"
            }`}
          >
            No Skill (default)
          </button>
          {skills.map((skill) => (
            <button
              key={skill.id}
              onClick={() => { setActiveSkillId(skill.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-[var(--color-surface-hover)] ${
                activeSkillId === skill.id ? "text-[var(--color-accent)]" : ""
              }`}
            >
              <span className="font-medium">{skill.name}</span>
              <span className="block text-[10px] text-[var(--color-text-muted)]">{skill.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
