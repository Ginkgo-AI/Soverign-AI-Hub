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
        lastMsg.content = [
          { type: "text" as const, text: userText },
          { type: "image_url" as const, image_url: { url: attachedImage } },
        ];
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
    <div className="flex flex-col h-full bg-[var(--color-bg)]">
      {/* ═══ Conversation Header ═══ */}
      {!isLaunchpad && (
        <div className="h-14 px-5 flex items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
          <button
            onClick={handleBackToLaunchpad}
            className="p-2 -ml-2 rounded-xl text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
            title="Back to conversations"
          >
            <ArrowLeft size={16} />
          </button>

          <h2 className="text-[13px] font-medium text-[var(--color-text-secondary)] truncate flex-1">
            {activeConversation?.title || "New Conversation"}
          </h2>

          <button
            onClick={() => setAgentMode(!agentMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
              agentMode
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${agentMode ? "bg-emerald-400" : "bg-[var(--color-text-muted)]"}`} />
            Agent
          </button>

          {agentIterations > 0 && (
            <span className="text-[11px] px-2.5 py-1 rounded-full bg-[var(--color-accent-subtle)] text-[var(--color-accent-hover)] font-mono tabular-nums">
              iter {agentIterations}
            </span>
          )}

          <ModelSelector
            selectedModel={selectedModel}
            selectedBackend={selectedBackend}
            onModelChange={(model, backend) => {
              setSelectedModel(model);
              setSelectedBackend(backend);
            }}
          />

          <div className="relative">
            <button
              onClick={() => setMoreMenuOpen(!moreMenuOpen)}
              className="p-2 rounded-xl text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
            >
              <MoreHorizontal size={16} />
            </button>
            {moreMenuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setMoreMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-2 z-40 w-60 bg-[var(--color-surface-raised)] border border-[var(--color-border)] rounded-xl shadow-2xl py-2">
                  <div className="px-3 py-2">
                    <MemoryIndicator />
                  </div>
                  {agentMode && (
                    <>
                      <div className="px-3 py-2 border-t border-[var(--color-border)]">
                        <SkillPickerComponent />
                      </div>
                      <div className="px-3 py-2 border-t border-[var(--color-border)]">
                        <ToolPicker enabledTools={enabledTools} onToolsChange={setEnabledTools} />
                      </div>
                    </>
                  )}
                  {activeConversation?.classificationLevel && (
                    <div className="px-3 py-2 border-t border-[var(--color-border)]">
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-[var(--color-unclassified)]/20 text-[var(--color-unclassified)] tracking-wide">
                        {activeConversation.classificationLevel}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <button
            onClick={() => setHistoryOpen(true)}
            className="p-2 rounded-xl text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
            title="Conversation history"
          >
            <Clock size={16} />
          </button>
        </div>
      )}

      {/* ═══ Main Content ═══ */}
      {isLoadingHistory ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-[var(--color-border)] border-t-[var(--color-accent)] rounded-full animate-spin" />
        </div>
      ) : isLaunchpad ? (
        /* ═══ Launchpad ═══ */
        <div className="flex-1 flex flex-col items-center px-6 relative overflow-y-auto">
          {/* Subtle ambient light */}
          <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[var(--color-accent)]/[0.03] rounded-full blur-[150px] pointer-events-none" />

          <div className="relative w-full max-w-[640px] mx-auto mt-[16vh]">
            {/* Minimal branding */}
            <div className="flex justify-center mb-6">
              <Logo size={40} compact />
            </div>

            <h1 className="text-[28px] font-semibold text-center tracking-tight mb-1">
              Sovereign <span className="gradient-text">AI</span>
            </h1>
            <p className="text-center text-[var(--color-text-muted)] text-[13px] mb-10">
              What would you like to work on?
            </p>

            {/* Hero input */}
            <div className="hero-input relative">
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
                placeholder="Ask anything..."
                rows={2}
                className="w-full bg-transparent px-5 pt-5 pb-16 text-[15px] resize-none focus:outline-none placeholder:text-[var(--color-text-muted)] max-h-[300px] leading-relaxed"
                style={{ border: "none", boxShadow: "none" }}
              />

              <div className="absolute bottom-0 left-0 right-0 px-4 py-3 flex items-center gap-2">
                {!attachedImage && (
                  <ImageUpload
                    onImageSelected={setAttachedImage}
                    onRemove={() => setAttachedImage(null)}
                    currentImage={null}
                    disabled={isStreaming}
                  />
                )}
                <VoiceInput onTranscription={handleVoiceTranscription} disabled={isStreaming} />
                <button
                  onClick={() => setAgentMode(!agentMode)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${
                    agentMode
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${agentMode ? "bg-emerald-400" : "bg-[var(--color-text-muted)]"}`} />
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
                    className="w-9 h-9 flex items-center justify-center rounded-xl btn-gradient disabled:opacity-20"
                  >
                    <Send size={15} />
                  </button>
                </div>
              </div>
            </div>

            {attachedImage && (
              <div className="mt-3">
                <ImageUpload
                  onImageSelected={setAttachedImage}
                  onRemove={() => setAttachedImage(null)}
                  currentImage={attachedImage}
                  disabled={isStreaming}
                />
              </div>
            )}

            {/* Suggestions — clean, airy */}
            <div className="mt-6 grid grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => setInput(s.action)}
                  className="flex items-start gap-2.5 text-left px-4 py-3 rounded-xl border border-[var(--color-border)] text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:border-[rgba(255,255,255,0.1)] hover:bg-[var(--color-surface)] transition-all"
                >
                  <ArrowUpRight size={13} className="shrink-0 mt-0.5 opacity-40" />
                  <span>{s.label}</span>
                </button>
              ))}
            </div>

            {/* Recent conversations */}
            {conversations.length > 0 && (
              <div className="mt-8 flex flex-wrap gap-2 justify-center">
                {conversations.slice(0, 5).map((conv) => (
                  <button
                    key={conv.id}
                    onClick={async () => {
                      setActiveConversation(conv.id);
                      await useChatStore.getState().loadConversation(conv.id);
                    }}
                    className="px-3 py-1.5 rounded-lg text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] transition-all truncate max-w-[180px]"
                  >
                    {conv.title}
                  </button>
                ))}
                {conversations.length > 5 && (
                  <button
                    onClick={() => setHistoryOpen(true)}
                    className="px-3 py-1.5 rounded-lg text-[11px] text-[var(--color-accent-hover)] bg-[var(--color-accent-subtle)] hover:bg-[var(--color-accent)]/20 transition-all"
                  >
                    View all
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ═══ Conversation Messages ═══ */
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
            {activeConversation.messages
              .filter((m) => m.role !== "system")
              .map((msg) => <MessageBubble key={msg.id} message={msg} />)}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {/* ═══ Work Mode Panel ═══ */}
      {!isLaunchpad && <WorkModePanel />}

      {/* ═══ Conversation Input ═══ */}
      {!isLaunchpad && (
        <>
          {attachedImage && (
            <div className="px-6 pb-2">
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

          <div className="px-6 py-5 bg-gradient-to-t from-[var(--color-bg)] via-[var(--color-bg)] to-transparent">
            <div className="max-w-3xl mx-auto">
              <div className="hero-input relative">
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
                  placeholder={attachedImage ? "Ask about the image..." : "Message..."}
                  disabled={isStreaming}
                  rows={1}
                  className="w-full bg-transparent px-5 pt-4 pb-13 text-[15px] resize-none focus:outline-none placeholder:text-[var(--color-text-muted)] max-h-[300px]"
                  style={{ border: "none", boxShadow: "none" }}
                />

                <div className="absolute bottom-0 left-0 right-0 px-4 py-3 flex items-center gap-2">
                  {!attachedImage && (
                    <ImageUpload
                      onImageSelected={setAttachedImage}
                      onRemove={() => setAttachedImage(null)}
                      currentImage={null}
                      disabled={isStreaming}
                    />
                  )}
                  <VoiceInput onTranscription={handleVoiceTranscription} disabled={isStreaming} />
                  {agentMode && (
                    <span className="text-[11px] text-emerald-400/80 font-medium px-1">Agent</span>
                  )}
                  <div className="ml-auto">
                    {isStreaming ? (
                      <button
                        onClick={handleStop}
                        className="w-9 h-9 flex items-center justify-center rounded-xl bg-red-500/90 hover:bg-red-500 text-white"
                      >
                        <Square size={13} />
                      </button>
                    ) : (
                      <button
                        onClick={handleSend}
                        disabled={!input.trim()}
                        className="w-9 h-9 flex items-center justify-center rounded-xl btn-gradient disabled:opacity-20"
                      >
                        <Send size={15} />
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
