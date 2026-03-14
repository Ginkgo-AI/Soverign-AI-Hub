"use client";

import { useEffect, useState } from "react";
import { apiJson } from "@/lib/api";

export function MemoryIndicator() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await apiJson<{ total_memories: number }>("/api/memory/context");
        setCount(data.total_memories);
      } catch {
        // Memory not available
      }
    };
    fetchCount();
  }, []);

  if (count === 0) return null;

  return (
    <span
      className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-purple-500/20 text-purple-400"
      title={`${count} memories active`}
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M12 2a7 7 0 0 1 7 7c0 3-2 5.5-4 7.5L12 22l-3-5.5C7 14.5 5 12 5 9a7 7 0 0 1 7-7z" />
      </svg>
      {count}
    </span>
  );
}
