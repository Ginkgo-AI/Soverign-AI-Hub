const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export type MessageContent =
  | string
  | null
  | Array<
      | { type: "text"; text: string }
      | { type: "image_url"; image_url: { url: string } }
    >;

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: MessageContent;
  tool_calls?: unknown[];
  tool_call_id?: string;
}

// Agent SSE event types
export interface ToolCallEvent {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultEvent {
  id: string;
  name: string;
  success: boolean;
  output: string;
  duration_ms: number;
  images?: Array<{ filename: string; data_url: string }>;
}

export interface AgentStatusEvent {
  type: "agent_start" | "agent_done" | "agent_error" | "iteration_start" | "task_created" | "task_started" | "task_completed" | "task_failed";
  iteration?: number;
  iterations?: number;
  tools?: string[];
  error?: string;
  // Work mode task fields
  task_id?: string;
  task_title?: string;
  task_status?: string;
  task_output?: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onToolCall?: (toolCall: ToolCallEvent) => void;
  onToolResult?: (result: ToolResultEvent) => void;
  onAgentStatus?: (status: AgentStatusEvent) => void;
  onDone: (conversationId?: string) => void;
  onError: (error: Error) => void;
}

export interface StreamOptions {
  model?: string;
  backend?: string;
  temperature?: number;
  maxTokens?: number;
  topP?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
  repeatPenalty?: number;
  tools?: unknown[];
  conversationId?: string;
  systemPrompt?: string;
  maxContextTokens?: number;
  agentMode?: boolean;
  agentTools?: string[];
  maxIterations?: number;
  // Osaurus-inspired extensions
  skillId?: string;
  workMode?: boolean;
  objective?: string;
}

export async function streamChat(
  messages: ChatMessage[],
  callbacks: StreamCallbacks,
  options: StreamOptions = {}
) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/v1/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        messages,
        stream: true,
        model: options.model || "",
        backend: options.backend || "vllm",
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 4096,
        top_p: options.topP,
        frequency_penalty: options.frequencyPenalty,
        presence_penalty: options.presencePenalty,
        repeat_penalty: options.repeatPenalty,
        tools: options.tools,
        conversation_id: options.conversationId,
        system_prompt: options.systemPrompt,
        max_context_tokens: options.maxContextTokens ?? 8192,
        agent_mode: options.agentMode ?? true,
        agent_tools: options.agentTools,
        max_iterations: options.maxIterations ?? 20,
        skill_id: options.skillId,
        work_mode: options.workMode,
        objective: options.objective,
      }),
    });
  } catch (err) {
    callbacks.onError(
      err instanceof Error ? err : new Error("Network error — is the API gateway running?")
    );
    return;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    callbacks.onError(new Error(`API error ${response.status}: ${text}`));
    return;
  }

  // Capture conversation ID from response header
  const conversationId = response.headers.get("X-Conversation-ID") || undefined;

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError(new Error("No response body"));
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let inThinkBlock = false;

  // Track current SSE event type (set by `event:` lines)
  let currentEventType: string | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        // Track SSE event type
        if (line.startsWith("event: ")) {
          currentEventType = line.slice(7).trim();
          continue;
        }

        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          callbacks.onDone(conversationId);
          return;
        }

        try {
          const parsed = JSON.parse(data);

          // Dispatch based on event type
          if (currentEventType === "tool_call" && callbacks.onToolCall) {
            callbacks.onToolCall(parsed as ToolCallEvent);
            currentEventType = null;
            continue;
          }

          if (currentEventType === "tool_result" && callbacks.onToolResult) {
            callbacks.onToolResult(parsed as ToolResultEvent);
            currentEventType = null;
            continue;
          }

          if (currentEventType === "agent_status" && callbacks.onAgentStatus) {
            callbacks.onAgentStatus(parsed as AgentStatusEvent);
            currentEventType = null;
            continue;
          }

          // Reset event type after processing
          currentEventType = null;

          // Default: standard content delta
          const delta = parsed.choices?.[0]?.delta;
          if (delta?.content) {
            // Filter out <think>...</think> reasoning blocks (Qwen3, etc.)
            let content = delta.content as string;
            if (inThinkBlock) {
              const endIdx = content.indexOf("</think>");
              if (endIdx !== -1) {
                inThinkBlock = false;
                content = content.slice(endIdx + 8);
              } else {
                content = "";
              }
            }
            if (!inThinkBlock && content.includes("<think>")) {
              const startIdx = content.indexOf("<think>");
              const before = content.slice(0, startIdx);
              const after = content.slice(startIdx + 7);
              const endIdx = after.indexOf("</think>");
              if (endIdx !== -1) {
                content = before + after.slice(endIdx + 8);
              } else {
                content = before;
                inThinkBlock = true;
              }
            }
            if (content) {
              callbacks.onToken(content);
            }
          }
          if (delta?.tool_calls && callbacks.onToolCall) {
            // Legacy: pass-through raw tool_calls from non-agent streaming
            for (const tc of delta.tool_calls) {
              callbacks.onToolCall(tc);
            }
          }
        } catch {
          // Skip malformed SSE lines
        }
      }
    }
    callbacks.onDone(conversationId);
  } catch (error) {
    callbacks.onError(
      error instanceof Error ? error : new Error(String(error))
    );
  }
}
