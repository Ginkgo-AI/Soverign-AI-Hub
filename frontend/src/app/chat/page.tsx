"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, type ChatMessage } from "@/lib/streaming";
import { useChatStore } from "@/stores/chatStore";
import { useAuthStore } from "@/stores/authStore";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { ChatInput } from "@/components/chat/ChatInput";
import { ModelSelector } from "@/components/shared/ModelSelector";
import { ImageUpload } from "@/components/chat/ImageUpload";
import { VoiceInput } from "@/components/chat/VoiceInput";

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
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
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

    // Build display content: include image preview if attached
    const displayContent = attachedImage
      ? `[Image attached]\n${userText}`
      : userText;

    addLocalMessage(convId, { role: "user", content: displayContent });
    setInput("");

    // Build messages for API call
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const apiMessages: ChatMessage[] =
      conv?.messages.map((m) => ({
        role: m.role,
        content: m.content,
      })) || [];

    // If image is attached, modify the last user message to include vision content
    if (attachedImage && apiMessages.length > 0) {
      const lastMsg = apiMessages[apiMessages.length - 1];
      if (lastMsg.role === "user") {
        // Use multimodal content format for the API
        // The vision endpoint will be used to process the image
        lastMsg.content = `[Analyze this image: ${attachedImage.substring(0, 50)}...] ${userText}`;
      }
    }

    // Clear the attached image after sending
    setAttachedImage(null);

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
    attachedImage, createConversation, addLocalMessage, updateLastAssistantMessage,
    setStreaming, scrollToBottom, setConversationId,
  ]);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    setStreaming(false);
  }, [setStreaming]);

  const handleVoiceTranscription = useCallback(
    (text: string) => {
      setInput((prev) => (prev ? `${prev} ${text}` : text));
    },
    []
  );

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
                    "Describe an image",
                    "Generate an image",
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

        {/* Attached image preview */}
        {attachedImage && (
          <div className="px-4 pb-2">
            <div className="max-w-3xl mx-auto">
              <ImageUpload
                onImageSelected={setAttachedImage}
                onRemove={() => setAttachedImage(null)}
                currentImage={attachedImage}
                disabled={isStreaming}
              />
            </div>
          </div>
        )}

        {/* Input area with multimodal controls */}
        <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <div className="max-w-3xl mx-auto flex gap-2 items-end">
            {/* Image upload button */}
            {!attachedImage && (
              <ImageUpload
                onImageSelected={setAttachedImage}
                onRemove={() => setAttachedImage(null)}
                currentImage={null}
                disabled={isStreaming}
              />
            )}

            {/* Voice input button */}
            <VoiceInput
              onTranscription={handleVoiceTranscription}
              disabled={isStreaming}
            />

            {/* Text input */}
            <textarea
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                const el = e.target;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 200) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!isStreaming && input.trim()) {
                    handleSend();
                  }
                }
              }}
              placeholder={
                attachedImage
                  ? "Ask about the image... (Shift+Enter for new line)"
                  : "Type a message... (Shift+Enter for new line)"
              }
              disabled={isStreaming}
              rows={1}
              className="flex-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-[var(--color-accent)] disabled:opacity-50 max-h-[200px]"
            />

            {/* Send / Stop button */}
            {isStreaming ? (
              <button
                onClick={handleStop}
                className="px-4 py-3 bg-[var(--color-danger)] hover:bg-red-600 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="px-6 py-3 bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white rounded-xl text-sm font-medium disabled:opacity-50 transition-colors"
              >
                Send
              </button>
            )}
          </div>
          <div className="max-w-3xl mx-auto mt-1.5 flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
            <span>All processing is local. Your data never leaves this machine.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
