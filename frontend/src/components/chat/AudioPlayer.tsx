"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { generateSpeech } from "@/lib/multimodal";

interface AudioPlayerProps {
  /** Pre-loaded audio URL (optional). */
  audioUrl?: string;
  /** Text to synthesize on demand (for "Read aloud" feature). */
  text?: string;
  /** Voice for TTS. */
  voice?: string;
}

export function AudioPlayer({ audioUrl, text, voice = "default" }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [currentUrl, setCurrentUrl] = useState<string | null>(audioUrl || null);
  const [error, setError] = useState<string | null>(null);

  // Cleanup object URL on unmount
  useEffect(() => {
    return () => {
      if (currentUrl && currentUrl.startsWith("blob:")) {
        URL.revokeObjectURL(currentUrl);
      }
    };
  }, [currentUrl]);

  const handleReadAloud = useCallback(async () => {
    if (!text) return;
    setError(null);

    // If we already have audio, just play/pause
    if (currentUrl && audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play();
        setIsPlaying(true);
      }
      return;
    }

    // Generate speech
    setIsLoading(true);
    try {
      const blob = await generateSpeech({ text, voice });
      const url = URL.createObjectURL(blob);
      setCurrentUrl(url);

      // Play after state update
      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current.playbackRate = playbackRate;
          audioRef.current.play();
          setIsPlaying(true);
        }
      }, 50);
    } catch (err) {
      setError(err instanceof Error ? err.message : "TTS failed");
    } finally {
      setIsLoading(false);
    }
  }, [text, voice, currentUrl, isPlaying, playbackRate]);

  const handlePlayPause = useCallback(() => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const cycleSpeed = useCallback(() => {
    const speeds = [0.75, 1.0, 1.25, 1.5, 2.0];
    const currentIdx = speeds.indexOf(playbackRate);
    const nextIdx = (currentIdx + 1) % speeds.length;
    const newRate = speeds[nextIdx];
    setPlaybackRate(newRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = newRate;
    }
  }, [playbackRate]);

  // "Read aloud" button (for assistant messages)
  if (text && !currentUrl) {
    return (
      <button
        onClick={handleReadAloud}
        disabled={isLoading}
        className="inline-flex items-center gap-1 px-2 py-1 text-[10px] rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors text-[var(--color-text-muted)] disabled:opacity-50"
        title="Read aloud"
      >
        {isLoading ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="animate-spin">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
            <path d="M12 2 A10 10 0 0 1 22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
        )}
        {isLoading ? "Loading..." : "Read aloud"}
      </button>
    );
  }

  // Inline audio player (for pre-loaded or just-generated audio)
  if (!currentUrl) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
      <audio
        ref={audioRef}
        src={currentUrl}
        onEnded={handleEnded}
        onPause={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
      />

      {/* Play/Pause */}
      <button
        onClick={handlePlayPause}
        className="p-1 hover:bg-[var(--color-surface-hover)] rounded transition-colors"
        title={isPlaying ? "Pause" : "Play"}
      >
        {isPlaying ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        )}
      </button>

      {/* Speed control */}
      <button
        onClick={cycleSpeed}
        className="px-1.5 py-0.5 text-[10px] font-mono rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
        title="Change playback speed"
      >
        {playbackRate}x
      </button>

      {error && (
        <span className="text-[10px] text-[var(--color-danger)]">{error}</span>
      )}
    </div>
  );
}
