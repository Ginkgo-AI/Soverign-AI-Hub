"use client";

import { useCallback, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/multimodal";

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
}

export function VoiceInput({ onTranscription, disabled }: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Prefer webm/opus, fall back to whatever is available
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());

        const audioBlob = new Blob(chunksRef.current, { type: mimeType });
        if (audioBlob.size === 0) {
          setError("No audio recorded.");
          return;
        }

        setIsTranscribing(true);
        try {
          const result = await transcribeAudio(audioBlob, {
            filename: `recording.${mimeType.includes("webm") ? "webm" : "mp4"}`,
          });
          if (result.text.trim()) {
            onTranscription(result.text.trim());
          } else {
            setError("No speech detected.");
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Transcription failed";
          setError(msg);
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start(250); // Collect data every 250ms
      setIsRecording(true);
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Microphone access denied.");
      } else {
        setError("Could not access microphone.");
      }
    }
  }, [onTranscription]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const handleClick = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || isTranscribing}
        className={`
          p-2.5 rounded-xl border transition-colors
          ${isRecording
            ? "border-[var(--color-danger)] bg-[var(--color-danger)]/10 animate-pulse"
            : "border-[var(--color-border)] hover:border-[var(--color-accent)] bg-[var(--color-surface)]"
          }
          ${isTranscribing ? "opacity-50" : ""}
          disabled:opacity-50
        `}
        title={
          isTranscribing
            ? "Transcribing..."
            : isRecording
              ? "Stop recording"
              : "Voice input"
        }
      >
        {isTranscribing ? (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            className="animate-spin text-[var(--color-text-muted)]"
          >
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
            <path d="M12 2 A10 10 0 0 1 22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={isRecording ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]"}
          >
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        )}
      </button>

      {error && (
        <div className="absolute top-full left-0 mt-1 text-[10px] text-[var(--color-danger)] whitespace-nowrap">
          {error}
        </div>
      )}
    </div>
  );
}
