"use client";

import { useCallback, useRef, useState } from "react";
import { fileToBase64 } from "@/lib/multimodal";

interface ImageUploadProps {
  onImageSelected: (base64DataUri: string) => void;
  onRemove: () => void;
  currentImage: string | null;
  disabled?: boolean;
}

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB
const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];

export function ImageUpload({
  onImageSelected,
  onRemove,
  currentImage,
  disabled,
}: ImageUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError("Unsupported format. Use PNG, JPEG, GIF, or WebP.");
        return;
      }

      if (file.size > MAX_FILE_SIZE) {
        setError("Image too large (max 20 MB).");
        return;
      }

      try {
        const base64 = await fileToBase64(file);
        onImageSelected(base64);
      } catch {
        setError("Failed to read image file.");
      }
    },
    [onImageSelected]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset so re-selecting the same file triggers onChange
      e.target.value = "";
    },
    [handleFile]
  );

  // If an image is already selected, show preview
  if (currentImage) {
    return (
      <div className="relative inline-block">
        <img
          src={currentImage}
          alt="Upload preview"
          className="h-16 w-16 rounded-lg object-cover border border-[var(--color-border)]"
        />
        <button
          onClick={onRemove}
          disabled={disabled}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-[var(--color-danger)] text-white text-xs flex items-center justify-center hover:bg-red-600 transition-colors"
          title="Remove image"
        >
          x
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        onChange={handleInputChange}
        className="hidden"
      />

      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        disabled={disabled}
        className={`
          p-2.5 rounded-xl border transition-colors
          ${isDragging
            ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
            : "border-[var(--color-border)] hover:border-[var(--color-accent)] bg-[var(--color-surface)]"
          }
          disabled:opacity-50
        `}
        title="Attach image"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-[var(--color-text-muted)]"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      </button>

      {error && (
        <div className="absolute top-full left-0 mt-1 text-[10px] text-[var(--color-danger)] whitespace-nowrap">
          {error}
        </div>
      )}
    </div>
  );
}
