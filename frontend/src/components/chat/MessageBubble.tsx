"use client";

import { MarkdownRenderer } from "./MarkdownRenderer";
import { ThinkingBlock } from "./ThinkingBlock";
import { AudioPlayer } from "./AudioPlayer";
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
