"""Schemas for multimodal capabilities: vision, audio, image generation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------

class VisionContentPart(BaseModel):
    """A single content part in a vision message (text or image_url)."""
    type: str  # "text" or "image_url"
    text: str | None = None
    image_url: dict[str, str] | None = None  # {"url": "data:image/...;base64,..."}


class VisionRequest(BaseModel):
    """Request for vision analysis / OCR."""
    model: str = ""
    prompt: str = "Describe this image in detail."
    images: list[str] = Field(
        default_factory=list,
        description="Base64-encoded images or data URIs",
    )
    max_tokens: int = 1024
    temperature: float = 0.3
    stream: bool = False
    backend: str = "vllm"


class VisionResponse(BaseModel):
    """Response from vision analysis."""
    id: str = Field(default_factory=lambda: f"vis-{uuid.uuid4().hex[:12]}")
    content: str
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))


# ---------------------------------------------------------------------------
# Audio — Transcription (Whisper)
# ---------------------------------------------------------------------------

class AudioTranscription(BaseModel):
    """Response from audio transcription."""
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict[str, Any]] | None = None


class TranscriptionRequest(BaseModel):
    """JSON-based transcription request (file upload handled via Form)."""
    model: str = "whisper-1"
    language: str | None = None
    prompt: str | None = None
    response_format: str = "json"  # json, text, srt, verbose_json, vtt
    temperature: float = 0.0


# ---------------------------------------------------------------------------
# Audio — Text-to-Speech (Piper)
# ---------------------------------------------------------------------------

class TTSRequest(BaseModel):
    """Request for text-to-speech synthesis."""
    model: str = "tts-1"
    input: str = Field(..., description="Text to synthesize")
    voice: str = "default"
    response_format: str = "wav"  # wav, mp3, opus, flac
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


class TTSResponse(BaseModel):
    """Metadata about TTS result (audio returned as stream)."""
    id: str = Field(default_factory=lambda: f"tts-{uuid.uuid4().hex[:12]}")
    format: str = "wav"
    duration: float | None = None


# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------

class ImageGenRequest(BaseModel):
    """Request for image generation (OpenAI-compatible)."""
    model: str = "stable-diffusion"
    prompt: str
    negative_prompt: str = ""
    n: int = Field(default=1, ge=1, le=4)
    size: str = "512x512"  # "512x512", "768x768", "1024x1024"
    quality: str = "standard"  # "standard", "hd"
    response_format: str = "url"  # "url" or "b64_json"
    # Extended params for SD
    steps: int = Field(default=30, ge=1, le=150)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=30.0)
    seed: int = -1
    enhance_prompt: bool = False


class ImageGenData(BaseModel):
    """A single generated image."""
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageGenResponse(BaseModel):
    """Response from image generation (OpenAI-compatible)."""
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    data: list[ImageGenData]


class ImageRecord(BaseModel):
    """Metadata for a stored generated image."""
    id: str
    prompt: str
    negative_prompt: str = ""
    filename: str
    url: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int
    model: str = ""
    created_at: datetime
