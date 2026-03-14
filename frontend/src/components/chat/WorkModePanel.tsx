"use client";

import { useChatStore } from "@/stores/chatStore";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-500/20 text-gray-400",
  running: "bg-blue-500/20 text-blue-400 animate-pulse",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  skipped: "bg-yellow-500/20 text-yellow-400",
};

export function WorkModePanel() {
  const { workMode, workTasks } = useChatStore();

  if (!workMode || workTasks.length === 0) return null;

  const completed = workTasks.filter((t) => t.status === "completed").length;
  const total = workTasks.length;
  const progressPct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium">Work Mode</span>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {completed}/{total} tasks ({progressPct}%)
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 bg-[var(--color-border)] rounded-full mb-3">
          <div
            className="h-full bg-[var(--color-accent)] rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* Task tree */}
        <div className="space-y-1">
          {workTasks.map((task, idx) => (
            <div key={task.id} className="flex items-center gap-2 text-xs">
              <span className="w-4 text-right text-[var(--color-text-muted)]">{idx + 1}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${STATUS_STYLES[task.status] || ""}`}>
                {task.status}
              </span>
              <span className="truncate flex-1">{task.title}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
