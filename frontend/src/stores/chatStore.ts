import { create } from "zustand";
import { apiJson } from "@/lib/api";
import type { ToolCallEvent, ToolResultEvent } from "@/lib/streaming";

function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts (HTTP on non-localhost)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export interface Message {
  id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  toolCalls?: unknown[];
  isStreaming?: boolean;
  timestamp: number;
  // Agent tool-call fields
  isToolCall?: boolean;
  toolName?: string;
  toolArguments?: Record<string, unknown>;
  toolCallId?: string;
  toolSuccess?: boolean;
  toolDuration?: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  model: string;
  backend: string;
  classificationLevel: string;
  messageCount: number;
  createdAt: number;
  updatedAt: number;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isStreaming: boolean;
  isLoadingHistory: boolean;

  // Agent mode state
  agentMode: boolean;
  enabledTools: string[];

  // Osaurus-inspired state
  activeSkillId: string | null;
  memoryEnabled: boolean;
  memoryCount: number;
  workMode: boolean;
  workTasks: Array<{id: string; title: string; status: string; output?: string}>;

  // API-backed actions
  fetchConversations: () => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  createConversation: (systemPrompt?: string) => Promise<string>;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;

  // Local actions for streaming
  setActiveConversation: (id: string | null) => void;
  addLocalMessage: (conversationId: string, message: Omit<Message, "id" | "timestamp">) => void;
  updateLastAssistantMessage: (conversationId: string, content: string) => void;
  setStreaming: (streaming: boolean) => void;
  setConversationId: (tempId: string, realId: string) => void;

  // Agent mode actions
  setAgentMode: (enabled: boolean) => void;
  setEnabledTools: (tools: string[]) => void;
  addToolCallMessage: (conversationId: string, toolCall: ToolCallEvent) => void;
  addToolResultMessage: (conversationId: string, result: ToolResultEvent) => void;

  // Osaurus-inspired actions
  setActiveSkillId: (id: string | null) => void;
  setMemoryEnabled: (enabled: boolean) => void;
  setMemoryCount: (count: number) => void;
  setWorkMode: (enabled: boolean) => void;
  setWorkTasks: (tasks: Array<{id: string; title: string; status: string; output?: string}>) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  isStreaming: false,
  isLoadingHistory: false,
  agentMode: true,
  enabledTools: [],
  activeSkillId: null,
  memoryEnabled: true,
  memoryCount: 0,
  workMode: false,
  workTasks: [],

  fetchConversations: async () => {
    try {
      const data = await apiJson<{
        conversations: Array<{
          id: string;
          title: string;
          model_id: string;
          classification_level: string;
          message_count: number;
          created_at: string;
          updated_at: string;
        }>;
      }>("/api/conversations");

      set({
        conversations: data.conversations.map((c) => ({
          id: c.id,
          title: c.title,
          messages: [],
          model: c.model_id || "",
          backend: "vllm",
          classificationLevel: c.classification_level,
          messageCount: c.message_count,
          createdAt: new Date(c.created_at).getTime(),
          updatedAt: new Date(c.updated_at).getTime(),
        })),
      });
    } catch {
      // Not authenticated or API not available — use local mode
    }
  },

  loadConversation: async (id: string) => {
    set({ isLoadingHistory: true, activeConversationId: id });
    try {
      const data = await apiJson<{
        id: string;
        title: string;
        model_id: string;
        classification_level: string;
        messages: Array<{
          id: string;
          role: string;
          content: string | null;
          tool_calls: unknown[] | null;
          tool_call_id: string | null;
          created_at: string;
        }>;
      }>(`/api/conversations/${id}`);

      set((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === id
            ? {
                ...c,
                title: data.title,
                messages: data.messages.map((m) => ({
                  id: m.id,
                  role: m.role as Message["role"],
                  content: m.content || "",
                  toolCalls: m.tool_calls || undefined,
                  toolCallId: m.tool_call_id || undefined,
                  // Infer tool-call display fields from persisted data
                  isToolCall: m.role === "assistant" && !!m.tool_calls?.length,
                  toolName: m.role === "tool" ? (m.content?.split(":")[0] || "tool") : undefined,
                  timestamp: new Date(m.created_at).getTime(),
                })),
              }
            : c
        ),
        isLoadingHistory: false,
      }));
    } catch {
      set({ isLoadingHistory: false });
    }
  },

  createConversation: async (systemPrompt?: string) => {
    const localId = generateUUID();
    const now = Date.now();

    const conversation: Conversation = {
      id: localId,
      title: "New Conversation",
      messages: [],
      model: "",
      backend: "vllm",
      classificationLevel: "UNCLASSIFIED",
      messageCount: 0,
      createdAt: now,
      updatedAt: now,
    };

    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: localId,
    }));

    return localId;
  },

  deleteConversation: async (id: string) => {
    try {
      await apiJson(`/api/conversations/${id}`, { method: "DELETE" });
    } catch {
      // Ignore — may not be persisted
    }
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    }));
  },

  renameConversation: async (id: string, title: string) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }));
    try {
      await apiJson(`/api/conversations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
    } catch {
      // Ignore
    }
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  addLocalMessage: (conversationId, message) => {
    const msg: Message = {
      ...message,
      id: generateUUID(),
      timestamp: Date.now(),
    };
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId
          ? { ...c, messages: [...c.messages, msg], updatedAt: Date.now() }
          : c
      ),
    }));
  },

  updateLastAssistantMessage: (conversationId, content) => {
    set((state) => ({
      conversations: state.conversations.map((c) => {
        if (c.id !== conversationId) return c;
        const messages = [...c.messages];
        const lastIdx = messages.length - 1;
        if (lastIdx >= 0 && messages[lastIdx].role === "assistant") {
          messages[lastIdx] = { ...messages[lastIdx], content };
        }
        return { ...c, messages };
      }),
    }));
  },

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setConversationId: (tempId, realId) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === tempId ? { ...c, id: realId } : c
      ),
      activeConversationId:
        state.activeConversationId === tempId ? realId : state.activeConversationId,
    }));
  },

  // Agent mode actions
  setAgentMode: (enabled) => set({ agentMode: enabled }),

  setEnabledTools: (tools) => set({ enabledTools: tools }),

  addToolCallMessage: (conversationId, toolCall) => {
    const msg: Message = {
      id: generateUUID(),
      role: "assistant",
      content: "",
      isToolCall: true,
      toolName: toolCall.name,
      toolArguments: toolCall.arguments,
      toolCallId: toolCall.id,
      timestamp: Date.now(),
    };
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId
          ? { ...c, messages: [...c.messages, msg], updatedAt: Date.now() }
          : c
      ),
    }));
  },

  addToolResultMessage: (conversationId, result) => {
    const msg: Message = {
      id: generateUUID(),
      role: "tool",
      content: result.output,
      toolName: result.name,
      toolCallId: result.id,
      toolSuccess: result.success,
      toolDuration: result.duration_ms,
      timestamp: Date.now(),
    };
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === conversationId
          ? { ...c, messages: [...c.messages, msg], updatedAt: Date.now() }
          : c
      ),
    }));
  },

  // Osaurus-inspired actions
  setActiveSkillId: (id) => set({ activeSkillId: id }),
  setMemoryEnabled: (enabled) => set({ memoryEnabled: enabled }),
  setMemoryCount: (count) => set({ memoryCount: count }),
  setWorkMode: (enabled) => set({ workMode: enabled }),
  setWorkTasks: (tasks) => set({ workTasks: tasks }),
}));
