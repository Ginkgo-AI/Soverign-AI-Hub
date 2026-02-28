"use client";

import { MarkdownRenderer } from "./MarkdownRenderer";
import { ThinkingBlock } from "./ThinkingBlock";
import type { Message } from "@/stores/chatStore";

interface MessageBubbleProps {
  message: Message;
}

/**
 * Parse thinking blocks from content.
 * Models may emit <think>...</think> or similar tags for chain-of-thought.
 */
function parseThinking(content: string): { thinking: string | null; response: string } {
  // Match <think>...</think> blocks (Qwen3, DeepSeek style)
  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
  if (thinkMatch) {
    const thinking = thinkMatch[1].trim();
    const response = content.replace(/<think>[\s\S]*?<\/think>/, "").trim();
    return { thinking, response };
  }
  return { thinking: null, response: content };
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isTool = message.role === "tool";

  if (isSystem) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="px-3 py-2 rounded text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)] border border-[var(--color-border)]">
          <span className="font-semibold">System:</span> {message.content}
        </div>
      </div>
    );
  }

  if (isTool) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="px-3 py-2 rounded text-xs font-mono bg-[#1a1a2e] border border-[var(--color-border)]">
          <span className="text-[var(--color-warning)] font-semibold">Tool Result:</span>
          <pre className="mt-1 whitespace-pre-wrap text-[var(--color-text-muted)]">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="max-w-3xl mx-auto flex justify-end">
        <div className="inline-block px-4 py-3 rounded-2xl rounded-br-sm text-sm bg-[var(--color-accent)] text-white max-w-[80%]">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  const { thinking, response } = parseThinking(message.content || "");

  return (
    <div className="max-w-3xl mx-auto">
      {thinking && <ThinkingBlock content={thinking} />}
      <div className="text-sm leading-relaxed">
        {response ? (
          <MarkdownRenderer content={response} />
        ) : message.isStreaming ? (
          <span className="inline-block w-2 h-4 bg-[var(--color-text-muted)] animate-pulse" />
        ) : null}
      </div>
    </div>
  );
}
