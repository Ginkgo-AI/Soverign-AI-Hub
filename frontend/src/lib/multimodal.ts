/**
 * Multimodal helper functions for vision, audio, and image generation.
 *
 * Handles binary data (Blob, File, base64) and communicates with the
 * gateway's multimodal endpoints.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

// ---------------------------------------------------------------------------
// Base64 / File utilities
// ---------------------------------------------------------------------------

export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result); // Returns data URI: data:mime;base64,...
    };
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

export function base64ToBlob(base64: string, mimeType: string): Blob {
  // Strip data URI prefix if present
  const raw = base64.includes(",") ? base64.split(",")[1] : base64;
  const bytes = atob(raw);
  const array = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    array[i] = bytes.charCodeAt(i);
  }
  return new Blob([array], { type: mimeType });
}

// ---------------------------------------------------------------------------
// Vision API
// ---------------------------------------------------------------------------

export interface VisionAnalyzeParams {
  images: string[]; // base64 or data URIs
  prompt?: string;
  model?: string;
  backend?: string;
  maxTokens?: number;
  stream?: boolean;
}

export interface VisionResponse {
  id: string;
  content: string;
  model: string;
  usage: Record<string, number>;
}

export async function analyzeImage(
  params: VisionAnalyzeParams
): Promise<VisionResponse> {
  const response = await fetch(`${API_URL}/v1/vision/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      images: params.images,
      prompt: params.prompt || "Describe this image in detail.",
      model: params.model || "",
      backend: params.backend || "vllm",
      max_tokens: params.maxTokens || 1024,
      stream: params.stream || false,
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`Vision API error ${response.status}: ${text}`);
  }

  return response.json();
}

export async function uploadImageForAnalysis(
  file: File,
  prompt: string = "Describe this image in detail."
): Promise<VisionResponse> {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("prompt", prompt);

  const response = await fetch(`${API_URL}/v1/vision/analyze`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`Vision API error ${response.status}: ${text}`);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Audio Transcription API (Whisper)
// ---------------------------------------------------------------------------

export interface TranscriptionResult {
  text: string;
  language?: string;
  duration?: number;
}

export async function transcribeAudio(
  audioBlob: Blob,
  options?: {
    filename?: string;
    language?: string;
    prompt?: string;
  }
): Promise<TranscriptionResult> {
  const formData = new FormData();
  formData.append(
    "file",
    audioBlob,
    options?.filename || "recording.wav"
  );
  formData.append("model", "whisper-1");

  if (options?.language) {
    formData.append("language", options.language);
  }
  if (options?.prompt) {
    formData.append("prompt", options.prompt);
  }

  const response = await fetch(`${API_URL}/v1/audio/transcriptions`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`Transcription error ${response.status}: ${text}`);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Text-to-Speech API (Piper)
// ---------------------------------------------------------------------------

export interface TTSParams {
  text: string;
  voice?: string;
  format?: string;
  speed?: number;
}

export async function generateSpeech(params: TTSParams): Promise<Blob> {
  const response = await fetch(`${API_URL}/v1/audio/speech`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      model: "tts-1",
      input: params.text,
      voice: params.voice || "default",
      response_format: params.format || "wav",
      speed: params.speed || 1.0,
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`TTS error ${response.status}: ${text}`);
  }

  return response.blob();
}

// ---------------------------------------------------------------------------
// Image Generation API
// ---------------------------------------------------------------------------

export interface ImageGenParams {
  prompt: string;
  negativePrompt?: string;
  n?: number;
  size?: string;
  steps?: number;
  cfgScale?: number;
  seed?: number;
  enhancePrompt?: boolean;
}

export interface GeneratedImage {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
}

export interface ImageGenResult {
  created: number;
  data: GeneratedImage[];
}

export async function generateImage(
  params: ImageGenParams
): Promise<ImageGenResult> {
  const response = await fetch(`${API_URL}/v1/images/generations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      prompt: params.prompt,
      negative_prompt: params.negativePrompt || "",
      n: params.n || 1,
      size: params.size || "512x512",
      steps: params.steps || 30,
      cfg_scale: params.cfgScale || 7.0,
      seed: params.seed ?? -1,
      enhance_prompt: params.enhancePrompt || false,
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`Image generation error ${response.status}: ${text}`);
  }

  return response.json();
}

export interface StoredImage {
  id: string;
  prompt: string;
  negative_prompt: string;
  filename: string;
  url: string;
  width: number;
  height: number;
  steps: number;
  cfg_scale: number;
  seed: number;
  model: string;
  created_at: string;
}

export async function fetchImageGallery(
  limit: number = 50,
  offset: number = 0
): Promise<StoredImage[]> {
  const response = await fetch(
    `${API_URL}/api/images?limit=${limit}&offset=${offset}`,
    {
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch image gallery: ${response.status}`);
  }

  return response.json();
}

export function getImageUrl(imageId: string): string {
  return `${API_URL}/api/images/${imageId}`;
}
