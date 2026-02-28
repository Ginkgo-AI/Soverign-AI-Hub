"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat, type ChatMessage } from "@/lib/streaming";
import { useChatStore } from "@/stores/chatStore";

export default function ChatPage() {
  const {
    conversations,
    activeConversationId,
    isStreaming,
    createConversation,
    setActiveConversation,
    addMessage,
    updateLastAssistantMessage,
    setStreaming,
  } = useChatStore();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId
  );

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isStreaming) return;

    let convId = activeConversationId;
    if (!convId) {
      convId = createConversation();
    }

    addMessage(convId, { role: "user", content: input.trim() });
    const userInput = input.trim();
    setInput("");

    // Build messages array for API
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const apiMessages: ChatMessage[] =
      conv?.messages.map((m) => ({
        role: m.role,
        content: m.content,
      })) || [];

    // Add placeholder for streaming response
    addMessage(convId, { role: "assistant", content: "", isStreaming: true });
    setStreaming(true);

    let accumulated = "";

    await streamChat(apiMessages, {
      onToken: (token) => {
        accumulated += token;
        updateLastAssistantMessage(convId!, accumulated);
        scrollToBottom();
      },
      onDone: () => {
        setStreaming(false);
        scrollToBottom();
      },
      onError: (error) => {
        updateLastAssistantMessage(
          convId!,
          accumulated || `Error: ${error.message}`
        );
        setStreaming(false);
      },
    });
  }, [
    input,
    isStreaming,
    activeConversationId,
    createConversation,
    addMessage,
    updateLastAssistantMessage,
    setStreaming,
    scrollToBottom,
  ]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {!activeConversation || activeConversation.messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <h2 className="text-2xl font-semibold mb-2">Start a conversation</h2>
              <p className="text-[var(--color-text-muted)]">
                All processing happens locally. Your data never leaves this machine.
              </p>
            </div>
          </div>
        ) : (
          activeConversation.messages.map((msg) => (
            <div
              key={msg.id}
              className={`max-w-3xl mx-auto ${
                msg.role === "user" ? "text-right" : ""
              }`}
            >
              <div
                className={`inline-block px-4 py-3 rounded-lg text-sm whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] border border-[var(--color-border)]"
                }`}
              >
                {msg.content || (msg.isStreaming ? "..." : "")}
              </div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">
                {msg.role}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-[var(--color-border)] p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message..."
            disabled={isStreaming}
            className="flex-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-accent)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="px-6 py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {isStreaming ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
