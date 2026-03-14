"use client";

import { MarkdownRenderer } from "./MarkdownRenderer";
import { ThinkingBlock } from "./ThinkingBlock";
import { AudioPlayer } from "./AudioPlayer";
import dynamic from "next/dynamic";
import { isChartData } from "./chartUtils";
import type { Message } from "@/stores/chatStore";

const AutoChart = dynamic(() => import("./AutoChart"), { ssr: false });

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

/**
 * Detect and extract inline images from message content.
 * Matches data URIs and /api/images/ URLs.
 */
function extractImages(content: string): { images: string[]; textContent: string } {
  const images: string[] = [];
  let textContent = content;

  // Match data URIs
  const dataUriRegex = /data:image\/[^;]+;base64,[A-Za-z0-9+/=]+/g;
  const dataMatches = content.match(dataUriRegex);
  if (dataMatches) {
    images.push(...dataMatches);
    textContent = textContent.replace(dataUriRegex, "").trim();
  }

  // Match /api/images/ URLs
  const imageUrlRegex = /\/api\/images\/[a-f0-9]+/g;
  const urlMatches = content.match(imageUrlRegex);
  if (urlMatches) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    images.push(...urlMatches.map((url) => `${apiUrl}${url}`));
    textContent = textContent.replace(imageUrlRegex, "").trim();
  }

  // Clean up "[Image attached]" markers
  textContent = textContent.replace(/\[Image attached\]\s*/g, "").trim();

  return { images, textContent };
}

/** Icon for tool categories */
function toolIcon(name: string): string {
  if (name.includes("python") || name.includes("bash") || name.includes("code")) return "\u25b6";
  if (name.includes("file")) return "\u2630";
  if (name.includes("search") || name.includes("rag")) return "\u2315";
  if (name.includes("calc")) return "\u2211";
  if (name.includes("http")) return "\u21c4";
  if (name.includes("image") || name.includes("vision")) return "\u25a3";
  return "\u2699";
}

/** Summarize tool arguments for compact display */
function summarizeArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return "";
  // Show the first meaningful argument value, truncated
  const [key, val] = entries[0];
  const str = typeof val === "string" ? val : JSON.stringify(val);
  const truncated = str.length > 80 ? str.slice(0, 77) + "..." : str;
  return `${key}: ${truncated}`;
}

/** Tool Call message (assistant calling a tool) */
function ToolCallBubble({ message }: { message: Message }) {
  const args = message.toolArguments || {};

  return (
    <div className="max-w-3xl mx-auto">
      <div className="px-3 py-2 rounded-lg text-xs bg-[var(--color-surface)] border border-[var(--color-border)] border-l-2 border-l-[var(--color-accent)]">
        <div className="flex items-center gap-2">
          <span className="text-base leading-none">{toolIcon(message.toolName || "")}</span>
          <span className="font-semibold text-[var(--color-accent)]">{message.toolName}</span>
        </div>
        {Object.keys(args).length > 0 && (
          <details className="mt-1.5">
            <summary className="cursor-pointer text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
              {summarizeArgs(args)}
            </summary>
            <pre className="mt-1 p-2 rounded bg-[#1a1a2e] text-[var(--color-text-muted)] overflow-x-auto text-[11px] leading-relaxed">
              {JSON.stringify(args, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

/** Tool Result message (result from tool execution) */
function ToolResultBubble({ message }: { message: Message }) {
  const success = message.toolSuccess !== false;
  const duration = message.toolDuration;

  return (
    <div className="max-w-3xl mx-auto">
      <div
        className={`px-3 py-2 rounded-lg text-xs border border-l-2 ${
          success
            ? "bg-[var(--color-surface)] border-[var(--color-border)] border-l-green-500"
            : "bg-red-950/20 border-red-900/30 border-l-red-500"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className={`w-2 h-2 rounded-full ${success ? "bg-green-500" : "bg-red-500"}`} />
          <span className="font-semibold text-[var(--color-text-muted)]">
            {message.toolName || "Tool"} {success ? "completed" : "failed"}
          </span>
          {duration != null && (
            <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] bg-[var(--color-border)]/50 text-[var(--color-text-muted)] font-mono">
              {duration}ms
            </span>
          )}
        </div>
        {message.content && (
          success && isChartData(message.content.trim()) ? (
            <AutoChart data={message.content.trim()} />
          ) : (
            <details open={!success || message.content.length < 300}>
              <summary className="cursor-pointer text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                {success ? "Output" : "Error details"}
              </summary>
              <pre className="mt-1 p-2 rounded bg-[#1a1a2e] text-[var(--color-text-muted)] overflow-x-auto max-h-64 overflow-y-auto text-[11px] leading-relaxed whitespace-pre-wrap">
                {message.content}
              </pre>
            </details>
          )
        )}
        {message.toolImages && message.toolImages.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.toolImages.map((img, i) => (
              <div key={i}>
                <p className="text-[10px] text-[var(--color-text-muted)] mb-1">{img.filename}</p>
                <img
                  src={img.data_url}
                  alt={img.filename}
                  className="rounded border border-[var(--color-border)] max-w-full"
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  // Agent tool-call messages
  if (message.isToolCall) {
    return <ToolCallBubble message={message} />;
  }

  // Agent tool-result messages
  if (message.role === "tool" && message.toolName) {
    return <ToolResultBubble message={message} />;
  }

  if (isSystem) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="px-3 py-2 rounded text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)] border border-[var(--color-border)]">
          <span className="font-semibold">System:</span> {message.content}
        </div>
      </div>
    );
  }

  // Legacy tool result (no toolName — from pre-agent messages)
  if (message.role === "tool") {
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

  // Extract images from content
  const { images, textContent } = extractImages(message.content || "");

  if (isUser) {
    return (
      <div className="max-w-3xl mx-auto flex justify-end">
        <div className="inline-block max-w-[80%]">
          {/* Inline image previews */}
          {images.length > 0 && (
            <div className="flex gap-2 mb-2 justify-end">
              {images.map((src, i) => (
                <img
                  key={i}
                  src={src}
                  alt={`Attached image ${i + 1}`}
                  className="h-24 w-24 rounded-lg object-cover border border-white/20"
                />
              ))}
            </div>
          )}
          {textContent && (
            <div className="px-4 py-3 rounded-2xl rounded-br-sm text-sm bg-[var(--color-accent)] text-white">
              {textContent}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Assistant message
  const { thinking, response } = parseThinking(textContent || "");

  return (
    <div className="max-w-3xl mx-auto">
      {thinking && <ThinkingBlock content={thinking} />}

      {/* Inline images in assistant response */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {images.map((src, i) => (
            <a key={i} href={src} target="_blank" rel="noopener noreferrer">
              <img
                src={src}
                alt={`Generated image ${i + 1}`}
                className="max-h-64 rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors"
              />
            </a>
          ))}
        </div>
      )}

      <div className="text-sm leading-relaxed">
        {response ? (
          <MarkdownRenderer content={response} />
        ) : message.isStreaming ? (
          <span className="inline-block w-2 h-4 bg-[var(--color-text-muted)] animate-pulse" />
        ) : null}
      </div>

      {/* Read aloud button for non-streaming assistant messages */}
      {!message.isStreaming && response && response.length > 10 && (
        <div className="mt-2">
          <AudioPlayer text={response} />
        </div>
      )}
    </div>
  );
}
