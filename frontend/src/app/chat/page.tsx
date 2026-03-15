"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat, type ChatMessage } from "@/lib/streaming";
import { useChatStore } from "@/stores/chatStore";
import { useAuthStore } from "@/stores/authStore";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { HistoryPanel } from "@/components/chat/HistoryPanel";
import { ModelSelector } from "@/components/shared/ModelSelector";
import Logo from "@/components/shared/Logo";
import { ImageUpload } from "@/components/chat/ImageUpload";
import { VoiceInput } from "@/components/chat/VoiceInput";
import { ToolPicker } from "@/components/chat/ToolPicker";
import { MemoryIndicator } from "@/components/chat/MemoryIndicator";
import { SkillPicker as SkillPickerComponent } from "@/components/chat/SkillPicker";
import { WorkModePanel } from "@/components/chat/WorkModePanel";
import {
  ArrowLeft,
  Clock,
  MoreHorizontal,
  Send,
  Square,
  ArrowUpRight,
} from "lucide-react";

export default function ChatPage() {
  const {
    conversations,
    activeConversationId,
    isStreaming,
    isLoadingHistory,
    agentMode,
    enabledTools,
    createConversation,
    addLocalMessage,
    updateLastAssistantMessage,
    addToolCallMessage,
    addToolResultMessage,
    setStreaming,
    setConversationId,
    setAgentMode,
    setEnabledTools,
    setActiveConversation,
    fetchConversations,
  } = useChatStore();

  const { loadFromStorage, isAuthenticated } = useAuthStore();

  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedBackend, setSelectedBackend] = useState("vllm");
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [agentIterations, setAgentIterations] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  const isLaunchpad = !activeConversation || activeConversation.messages.length === 0;

  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus();
    }
  }, [activeConversationId, isStreaming]);

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
    const displayContent = attachedImage
      ? `[Image attached]\n${userText}`
      : userText;

    addLocalMessage(convId, { role: "user", content: displayContent });
    setInput("");
    setAgentIterations(0);

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId);
    const apiMessages: ChatMessage[] =
      conv?.messages
        .filter((m) => !m.isToolCall)
        .map((m) => ({
          role: m.role,
          content: m.content,
          ...(m.toolCallId && m.role === "tool" ? { tool_call_id: m.toolCallId } : {}),
        })) || [];

    if (attachedImage && apiMessages.length > 0) {
      const lastMsg = apiMessages[apiMessages.length - 1];
      if (lastMsg.role === "user") {
        lastMsg.content = `[Analyze this image: ${attachedImage.substring(0, 50)}...] ${userText}`;
      }
    }

    setAttachedImage(null);
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
      onToolCall: (toolCall) => {
        const currentConv = useChatStore.getState().conversations.find((c) => c.id === convId);
        const lastMsg = currentConv?.messages[currentConv.messages.length - 1];
        if (lastMsg?.isStreaming && !lastMsg.content) {
          useChatStore.setState((state) => ({
            conversations: state.conversations.map((c) => {
              if (c.id !== convId) return c;
              const msgs = c.messages.slice(0, -1);
              return { ...c, messages: msgs };
            }),
          }));
        }
        addToolCallMessage(convId!, toolCall);
        scrollToBottom();
      },
      onToolResult: (result) => {
        addToolResultMessage(convId!, result);
        addLocalMessage(convId!, { role: "assistant", content: "", isStreaming: true });
        accumulated = "";
        scrollToBottom();
      },
      onAgentStatus: (status) => {
        if (status.type === "iteration_start" && status.iteration) {
          setAgentIterations(status.iteration);
        }
        if (status.type === "agent_error") {
          updateLastAssistantMessage(convId!, `Agent error: ${status.error}`);
        }
        if (status.type === "agent_done") {
          setAgentIterations(0);
        }
      },
      onDone: (returnedConvId) => {
        if (returnedConvId && convId && returnedConvId !== convId) {
          setConversationId(convId, returnedConvId);
        }
        setStreaming(false);
        setAgentIterations(0);
        scrollToBottom();
      },
      onError: (error) => {
        updateLastAssistantMessage(
          convId!,
          accumulated || `Error: ${error.message}`
        );
        setStreaming(false);
        setAgentIterations(0);
      },
    }, {
      model: selectedModel,
      backend: selectedBackend,
      conversationId: activeConversationId || undefined,
      agentMode,
      agentTools: enabledTools.length > 0 ? enabledTools : undefined,
    });
  }, [
    input, isStreaming, activeConversationId, selectedModel, selectedBackend,
    attachedImage, agentMode, enabledTools, createConversation, addLocalMessage,
    updateLastAssistantMessage, addToolCallMessage, addToolResultMessage,
    setStreaming, scrollToBottom, setConversationId,
  ]);

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    setStreaming(false);
    setAgentIterations(0);
  }, [setStreaming]);

  const handleVoiceTranscription = useCallback(
    (text: string) => {
      setInput((prev) => (prev ? `${prev} ${text}` : text));
    },
    []
  );

  const handleBackToLaunchpad = () => {
    setActiveConversation(null);
  };

  const SUGGESTIONS = [
    { label: "Analyze a document from Knowledge Base", action: "Search my knowledge base and analyze " },
    { label: "Write and run code", action: "Write code to " },
    { label: "Research with web search", action: "Research " },
    { label: "Build an automated workflow", action: "Create a workflow that " },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* ═══ Conversation Header (only when in a conversation) ═══ */}
      {!isLaunchpad && (
        <div className="px-4 py-2.5 border-b border-[var(--color-border)] bg-[var(--color-surface)] flex items-center gap-3">
          {/* Back button */}
          <button
            onClick={handleBackToLaunchpad}
            className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04] transition-colors"
            title="Back to conversations"
          >
            <ArrowLeft size={18} />
          </button>

          {/* Title */}
          <h2 className="text-sm font-medium truncate flex-1">
            {activeConversation?.title || "New Conversation"}
          </h2>

          {/* Agent indicator */}
          <button
            onClick={() => setAgentMode(!agentMode)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
            style={{
              background: agentMode ? "rgba(34, 197, 94, 0.15)" : "rgba(255,255,255,0.04)",
              color: agentMode ? "#22c55e" : "var(--color-text-muted)",
            }}
            title={agentMode ? "Agent mode on" : "Agent mode off"}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${agentMode ? "bg-green-400" : "bg-[var(--color-text-muted)]"}`} />
            Agent
          </button>

          {/* Agent iteration indicator */}
          {agentIterations > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-accent)]/20 text-[var(--color-accent)] font-mono">
              iter {agentIterations}
            </span>
          )}

          {/* Model selector */}
          <ModelSelector
            selectedModel={selectedModel}
            selectedBackend={selectedBackend}
            onModelChange={(model, backend) => {
              setSelectedModel(model);
              setSelectedBackend(backend);
            }}
          />

          {/* More menu */}
          <div className="relative">
            <button
              onClick={() => setMoreMenuOpen(!moreMenuOpen)}
              className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04] transition-colors"
            >
              <MoreHorizontal size={18} />
            </button>
            {moreMenuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setMoreMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 z-40 w-56 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl py-1">
                  <div className="px-3 py-2">
                    <MemoryIndicator />
                  </div>
                  {agentMode && (
                    <>
                      <div className="px-3 py-2 border-t border-[var(--color-border)]">
                        <SkillPickerComponent />
                      </div>
                      <div className="px-3 py-2 border-t border-[var(--color-border)]">
                        <ToolPicker
                          enabledTools={enabledTools}
                          onToolsChange={setEnabledTools}
                        />
                      </div>
                    </>
                  )}
                  {activeConversation?.classificationLevel && (
                    <div className="px-3 py-2 border-t border-[var(--color-border)]">
                      <span className="px-2 py-0.5 text-xs font-bold rounded bg-[var(--color-unclassified)]/20 text-[var(--color-unclassified)]">
                        {activeConversation.classificationLevel}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* History button */}
          <button
            onClick={() => setHistoryOpen(true)}
            className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.04] transition-colors"
            title="Conversation history"
          >
            <Clock size={18} />
          </button>
        </div>
      )}

      {/* ═══ Main Content ═══ */}
      {isLoadingHistory ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-[var(--color-text-muted)]">Loading conversation...</p>
        </div>
      ) : isLaunchpad ? (
        /* ═══ Launchpad Empty State ═══ */
        <div className="flex-1 flex flex-col items-center justify-center px-4 relative">
          {/* Ambient glow */}
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-[var(--color-accent)]/[0.03] rounded-full blur-[120px] pointer-events-none" />

          <div className="relative w-full max-w-2xl mx-auto" style={{ marginTop: "-8vh" }}>
            {/* Logo */}
            <div className="flex justify-center mb-4">
              <Logo size={56} compact />
            </div>

            {/* Title */}
            <h1 className="text-2xl font-bold text-center mb-2">
              Sovereign <span className="gradient-text">AI Hub</span>
            </h1>
            <p className="text-center text-[var(--color-text-muted)] text-sm mb-8">
              What would you like to work on?
            </p>

            {/* Input area */}
            <div className="relative rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg focus-within:border-[var(--color-accent)] focus-within:shadow-[0_0_0_2px_rgba(59,130,246,0.1)] transition-all">
              <textarea
                ref={inputRef}
                autoFocus
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  const el = e.target;
                  el.style.height = "auto";
                  el.style.height = Math.min(el.scrollHeight, 300) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!isStreaming && input.trim()) handleSend();
                  }
                }}
                placeholder="Type a message, paste a doc, or try a suggestion below..."
                rows={3}
                className="w-full bg-transparent px-4 pt-4 pb-14 text-sm resize-none focus:outline-none placeholder:text-[var(--color-text-muted)]/60 max-h-[300px]"
                style={{ border: "none", boxShadow: "none" }}
              />

              {/* Bottom bar inside input */}
              <div className="absolute bottom-0 left-0 right-0 px-3 py-2.5 flex items-center gap-2">
                {!attachedImage && (
                  <ImageUpload
                    onImageSelected={setAttachedImage}
                    onRemove={() => setAttachedImage(null)}
                    currentImage={null}
                    disabled={isStreaming}
                  />
                )}
                <VoiceInput
                  onTranscription={handleVoiceTranscription}
                  disabled={isStreaming}
                />
                <button
                  onClick={() => setAgentMode(!agentMode)}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors"
                  style={{
                    background: agentMode ? "rgba(34, 197, 94, 0.15)" : "transparent",
                    color: agentMode ? "#22c55e" : "var(--color-text-muted)",
                  }}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${agentMode ? "bg-green-400" : "bg-[var(--color-text-muted)]"}`} />
                  Agent
                </button>

                <div className="ml-auto flex items-center gap-2">
                  <ModelSelector
                    selectedModel={selectedModel}
                    selectedBackend={selectedBackend}
                    onModelChange={(model, backend) => {
                      setSelectedModel(model);
                      setSelectedBackend(backend);
                    }}
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isStreaming}
                    className="p-2 rounded-lg btn-gradient disabled:opacity-30 disabled:transform-none"
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* Attached image preview */}
            {attachedImage && (
              <div className="mt-2">
                <ImageUpload
                  onImageSelected={setAttachedImage}
                  onRemove={() => setAttachedImage(null)}
                  currentImage={attachedImage}
                  disabled={isStreaming}
                />
              </div>
            )}

            {/* Suggestions */}
            <div className="mt-4 space-y-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => setInput(s.action)}
                  className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-white/[0.03] transition-colors"
                >
                  <ArrowUpRight size={14} className="shrink-0 opacity-50" />
                  {s.label}
                </button>
              ))}
            </div>

            {/* Recent conversations as chips */}
            {conversations.length > 0 && (
              <div className="mt-6 flex flex-wrap gap-2 justify-center">
                {conversations.slice(0, 5).map((conv) => (
                  <button
                    key={conv.id}
                    onClick={async () => {
                      setActiveConversation(conv.id);
                      await useChatStore.getState().loadConversation(conv.id);
                    }}
                    className="px-3 py-1.5 rounded-full text-xs text-[var(--color-text-muted)] bg-white/[0.03] border border-[var(--color-border)] hover:bg-white/[0.06] hover:text-[var(--color-text)] transition-colors truncate max-w-[200px]"
                  >
                    {conv.title}
                  </button>
                ))}
                {conversations.length > 5 && (
                  <button
                    onClick={() => setHistoryOpen(true)}
                    className="px-3 py-1.5 rounded-full text-xs text-[var(--color-accent)] bg-[var(--color-accent)]/10 hover:bg-[var(--color-accent)]/20 transition-colors"
                  >
                    View all
                  </button>
                )}
              </div>
            )}

            <p className="text-center text-xs text-[var(--color-text-muted)]/50 mt-6">
              Drop files here to start a conversation
            </p>
          </div>
        </div>
      ) : (
        /* ═══ Conversation Messages ═══ */
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {activeConversation.messages
            .filter((m) => m.role !== "system")
            .map((msg) => <MessageBubble key={msg.id} message={msg} />)}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* ═══ Work Mode Panel ═══ */}
      {!isLaunchpad && <WorkModePanel />}

      {/* ═══ Conversation Input (only when in active conversation) ═══ */}
      {!isLaunchpad && (
        <>
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

          {/* Input area */}
          <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-4">
            <div className="max-w-3xl mx-auto">
              <div className="relative rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] focus-within:border-[var(--color-accent)] focus-within:shadow-[0_0_0_2px_rgba(59,130,246,0.1)] transition-all">
                <textarea
                  ref={isLaunchpad ? undefined : inputRef}
                  autoFocus
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value);
                    const el = e.target;
                    el.style.height = "auto";
                    el.style.height = Math.min(el.scrollHeight, 300) + "px";
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      if (!isStreaming && input.trim()) handleSend();
                    }
                  }}
                  placeholder={
                    attachedImage
                      ? "Ask about the image..."
                      : "Message Sovereign AI..."
                  }
                  disabled={isStreaming}
                  rows={1}
                  className="w-full bg-transparent px-4 pt-3 pb-11 text-sm resize-none focus:outline-none placeholder:text-[var(--color-text-muted)]/60 max-h-[300px]"
                  style={{ border: "none", boxShadow: "none" }}
                />

                {/* Bottom bar inside input */}
                <div className="absolute bottom-0 left-0 right-0 px-3 py-2 flex items-center gap-1.5">
                  {!attachedImage && (
                    <ImageUpload
                      onImageSelected={setAttachedImage}
                      onRemove={() => setAttachedImage(null)}
                      currentImage={null}
                      disabled={isStreaming}
                    />
                  )}
                  <VoiceInput
                    onTranscription={handleVoiceTranscription}
                    disabled={isStreaming}
                  />
                  {agentMode && (
                    <span className="text-xs text-green-400 px-1.5">Agent</span>
                  )}
                  <div className="ml-auto">
                    {isStreaming ? (
                      <button
                        onClick={handleStop}
                        className="p-2 rounded-lg bg-[var(--color-danger)] hover:bg-red-600 text-white transition-colors"
                      >
                        <Square size={14} />
                      </button>
                    ) : (
                      <button
                        onClick={handleSend}
                        disabled={!input.trim()}
                        className="p-2 rounded-lg btn-gradient disabled:opacity-30 disabled:transform-none"
                      >
                        <Send size={16} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ═══ History Panel ═══ */}
      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </div>
  );
}
