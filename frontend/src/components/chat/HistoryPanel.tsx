"use client";

import { useEffect } from "react";
import { X, Trash2 } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";

export function HistoryPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const {
    conversations,
    activeConversationId,
    setActiveConversation,
    loadConversation,
    deleteConversation,
  } = useChatStore();

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) {
      document.addEventListener("keydown", handleKey);
      return () => document.removeEventListener("keydown", handleKey);
    }
  }, [open, onClose]);

  const handleSelect = async (id: string) => {
    setActiveConversation(id);
    await loadConversation(id);
    onClose();
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 bottom-0 z-50 w-80 bg-[var(--color-surface)] border-l border-[var(--color-border)] shadow-2xl flex flex-col animate-slide-in-right"
        style={{ paddingTop: "22px", paddingBottom: "22px" }}
      >
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Conversation History</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/5"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {conversations.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)] p-4 text-center">
              No conversations yet
            </p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center rounded-lg px-3 py-2.5 text-sm cursor-pointer transition-colors ${
                  conv.id === activeConversationId
                    ? "bg-white/[0.06] text-[var(--color-text)]"
                    : "text-[var(--color-text-muted)] hover:bg-white/[0.03] hover:text-[var(--color-text)]"
                }`}
                onClick={() => handleSelect(conv.id)}
              >
                <span className="flex-1 truncate">{conv.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-all ml-2"
                  title="Delete conversation"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
