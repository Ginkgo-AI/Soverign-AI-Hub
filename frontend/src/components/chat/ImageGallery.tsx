"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchImageGallery, getImageUrl, type StoredImage } from "@/lib/multimodal";

interface ImageGalleryProps {
  /** Called when the user selects an image to re-use as input. */
  onSelectImage?: (imageUrl: string) => void;
}

export function ImageGallery({ onSelectImage }: ImageGalleryProps) {
  const [images, setImages] = useState<StoredImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadImages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchImageGallery();
      setImages(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load images");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadImages();
  }, [loadImages]);

  const selectedImage = images.find((img) => img.id === selectedId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-[var(--color-text-muted)]">Loading gallery...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2">
        <p className="text-sm text-[var(--color-danger)]">{error}</p>
        <button
          onClick={loadImages}
          className="text-xs text-[var(--color-accent)] hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-[var(--color-text-muted)]">No generated images yet.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Enlarged view */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setSelectedId(null)}
        >
          <div
            className="relative max-w-[90vw] max-h-[90vh] bg-[var(--color-bg)] rounded-xl overflow-hidden shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={getImageUrl(selectedImage.id)}
              alt={selectedImage.prompt}
              className="max-w-full max-h-[75vh] object-contain"
            />
            <div className="p-4 space-y-2">
              <p className="text-sm">{selectedImage.prompt}</p>
              <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
                <span>
                  {selectedImage.width}x{selectedImage.height}
                </span>
                <span>Steps: {selectedImage.steps}</span>
                <span>CFG: {selectedImage.cfg_scale}</span>
                <span>Seed: {selectedImage.seed}</span>
              </div>
              <div className="flex gap-2">
                <a
                  href={getImageUrl(selectedImage.id)}
                  download={selectedImage.filename}
                  className="px-3 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  Download
                </a>
                {onSelectImage && (
                  <button
                    onClick={() => {
                      onSelectImage(getImageUrl(selectedImage.id));
                      setSelectedId(null);
                    }}
                    className="px-3 py-1 text-xs rounded border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors"
                  >
                    Use as input
                  </button>
                )}
                <button
                  onClick={() => setSelectedId(null)}
                  className="px-3 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors ml-auto"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Grid view */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {images.map((img) => (
          <button
            key={img.id}
            onClick={() => setSelectedId(img.id)}
            className="group relative aspect-square rounded-lg overflow-hidden border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors"
          >
            <img
              src={getImageUrl(img.id)}
              alt={img.prompt}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <p className="text-[10px] text-white line-clamp-2">{img.prompt}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
