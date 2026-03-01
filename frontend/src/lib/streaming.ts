const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: unknown[];
  tool_call_id?: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onToolCall?: (toolCall: unknown) => void;
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

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          callbacks.onDone(conversationId);
          return;
        }

        try {
          const parsed = JSON.parse(data);
          const delta = parsed.choices?.[0]?.delta;
          if (delta?.content) {
            callbacks.onToken(delta.content);
          }
          if (delta?.tool_calls && callbacks.onToolCall) {
            callbacks.onToolCall(delta.tool_calls);
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
