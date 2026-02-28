"""Vision service -- image understanding via multimodal LLM models.

Routes image + text queries to vLLM which supports multimodal models
(LLaVA, Llama Vision, Qwen2-VL) using the OpenAI Vision API message format.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

# Supported image MIME types
_SUPPORTED_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}


def _ensure_data_uri(image: str) -> str:
    """Convert raw base64 to a data URI if it isn't one already."""
    if image.startswith("data:"):
        return image
    # Try to detect format from the first bytes, default to jpeg
    return f"data:image/jpeg;base64,{image}"


def _build_vision_messages(
    prompt: str,
    images: list[str],
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Build OpenAI Vision API formatted messages with image_url content parts."""
    messages: list[dict[str, Any]] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Build multipart content for user message
    content_parts: list[dict[str, Any]] = []

    # Add images first
    for img in images:
        data_uri = _ensure_data_uri(img)
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": data_uri},
        })

    # Add the text prompt
    content_parts.append({"type": "text", "text": prompt})

    messages.append({"role": "user", "content": content_parts})
    return messages


async def analyze_image(
    images: list[str],
    prompt: str = "Describe this image in detail.",
    model: str = "",
    backend: str = "vllm",
    max_tokens: int = 1024,
    temperature: float = 0.3,
    stream: bool = False,
    system_prompt: str | None = None,
) -> dict | AsyncIterator[bytes]:
    """
    Analyze one or more images with a text prompt.

    Args:
        images: List of base64-encoded images or data URIs.
        prompt: Text query about the image(s).
        model: Model name (empty = backend default).
        backend: LLM backend to use.
        max_tokens: Max response tokens.
        temperature: Sampling temperature.
        stream: Whether to stream the response.
        system_prompt: Optional system instruction.

    Returns:
        OpenAI chat completion response dict, or async byte stream if streaming.
    """
    if not images:
        raise ValueError("At least one image is required")

    messages = _build_vision_messages(prompt, images, system_prompt)

    logger.info(
        "Vision analysis: %d image(s), prompt=%s, model=%s, backend=%s",
        len(images),
        prompt[:80],
        model,
        backend,
    )

    return await llm_backend.chat_completion(
        messages=messages,
        model=model,
        backend=backend,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )


async def extract_text(
    images: list[str],
    model: str = "",
    backend: str = "vllm",
    max_tokens: int = 2048,
    language_hint: str | None = None,
) -> dict:
    """
    OCR-style text extraction from image(s).

    Uses a specialized prompt to extract all visible text.
    """
    prompt = (
        "Extract all visible text from this image. "
        "Preserve the layout and formatting as much as possible. "
        "Return only the extracted text, no additional commentary."
    )
    if language_hint:
        prompt += f" The text is primarily in {language_hint}."

    return await llm_backend.chat_completion(
        messages=_build_vision_messages(prompt, images),
        model=model,
        backend=backend,
        temperature=0.1,
        max_tokens=max_tokens,
        stream=False,
    )


def validate_image_base64(data: str) -> bool:
    """Validate that a string is valid base64-encoded image data."""
    try:
        # Strip data URI prefix if present
        if data.startswith("data:"):
            parts = data.split(",", 1)
            if len(parts) != 2:
                return False
            mime = parts[0].split(";")[0].replace("data:", "")
            if mime not in _SUPPORTED_MIMES:
                return False
            data = parts[1]
        # Try to decode
        decoded = base64.b64decode(data, validate=True)
        return len(decoded) > 0
    except Exception:
        return False
