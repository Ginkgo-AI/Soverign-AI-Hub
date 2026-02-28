"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, type ChatMessage } from "@/lib/streaming";
import { useChatStore } from "@/stores/chatStore";
import { useAuthStore } from "@/stores/authStore";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { ChatInput } from "@/components/chat/ChatInput";
import { ModelSelector } from "@/components/shared/ModelSelector";

export default function ChatPage() {
  const {
    conversations,
    activeConversationId,
    isStreaming,
    isLoadingHistory,
    createConversation,
    addLocalMessage,
    updateLastAssistantMessage,
    setStreaming,
    setConversationId,
    fetchConversations,
  } = useChatStore();

  const { loadFromStorage, isAuthenticated } = useAuthStore();

  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedBackend, setSelectedBackend] = useState("vllm");
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load auth and conversation history on mount
  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchConversations();
    }
  }, [isAuthenticated, fetchConversations]);

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
      convId = await createConversation();
    }

    const userText = input.trim();
    addLocalMessage(convId, { role: "user", content: userText });
    setInput("");

    // Build messages for API call
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const apiMessages: ChatMessage[] =
      conv?.messages.map((m) => ({
        role: m.role,
        content: m.content,
      })) || [];

    // Add streaming placeholder
    addLocalMessage(convId, { role: "assistant", content: "", isStreaming: true });
    setStreaming(true);
    scrollToBottom();

    let accumulated = "";
    abortControllerRef.current = new AbortController();

    await streamChat(apiMessages, {
      onToken: (token) => {
        accumulated += token;
        updateLastAssistantMessage(convId!, accumulated);
        scrollToBottom();
      },
      onDone: (returnedConvId) => {
        // Update local ID with server-assigned conversation ID
        if (returnedConvId && convId && returnedConvId !== convId) {
          setConversationId(convId, returnedConvId);
        }
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
    }, {
      model: selectedModel,
      backend: selectedBackend,
      conversationId: activeConversationId || undefined,
    });
  }, [
    input, isStreaming, activeConversationId, selectedModel, selectedBackend,
    createConversation, addLocalMessage, updateLastAssistantMessage, setStreaming, scrollToBottom,
  ]);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    setStreaming(false);
  }, [setStreaming]);

  return (
    <div className="flex h-full">
      {/* Conversation history sidebar */}
      <ConversationSidebar />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium truncate max-w-xs">
              {activeConversation?.title || "New Conversation"}
            </h2>
            {activeConversation?.classificationLevel && (
              <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-[var(--color-unclassified)]/20 text-[var(--color-unclassified)]">
                {activeConversation.classificationLevel}
              </span>
            )}
          </div>
          <ModelSelector
            selectedModel={selectedModel}
            selectedBackend={selectedBackend}
            onModelChange={(model, backend) => {
              setSelectedModel(model);
              setSelectedBackend(backend);
            }}
          />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {isLoadingHistory ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-[var(--color-text-muted)]">Loading conversation...</p>
            </div>
          ) : !activeConversation || activeConversation.messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md">
                <h2 className="text-2xl font-semibold mb-2">Sovereign AI Hub</h2>
                <p className="text-[var(--color-text-muted)] text-sm mb-6">
                  All processing happens locally on your hardware.
                  No data leaves this machine.
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    "Summarize a document",
                    "Write a report",
                    "Analyze data",
                    "Generate code",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setInput(suggestion)}
                      className="px-3 py-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-left text-[var(--color-text-muted)]"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            activeConversation.messages
              .filter((m) => m.role !== "system")
              .map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  );
}
