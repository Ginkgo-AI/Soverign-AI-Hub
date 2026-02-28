"use client";

import { useChatStore } from "@/stores/chatStore";

export function ConversationSidebar() {
  const {
    conversations,
    activeConversationId,
    setActiveConversation,
    loadConversation,
    createConversation,
    deleteConversation,
  } = useChatStore();

  const handleNew = async () => {
    await createConversation();
  };

  const handleSelect = async (id: string) => {
    setActiveConversation(id);
    await loadConversation(id);
  };

  return (
    <div className="w-64 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col h-full">
      <div className="p-3 border-b border-[var(--color-border)]">
        <button
          onClick={handleNew}
          className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-left"
        >
          + New Conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {conversations.length === 0 && (
          <p className="text-xs text-[var(--color-text-muted)] p-3 text-center">
            No conversations yet
          </p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
              conv.id === activeConversationId
                ? "bg-[var(--color-surface-hover)] text-[var(--color-text)]"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}
            onClick={() => handleSelect(conv.id)}
          >
            <span className="flex-1 truncate">{conv.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-all ml-2 text-xs"
              title="Delete conversation"
            >
              x
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
