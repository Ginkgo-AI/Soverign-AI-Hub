"""Whisper service -- speech-to-text via whisper.cpp server.

whisper.cpp exposes an OpenAI-compatible /inference endpoint that accepts
audio files and returns transcriptions.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_FORMATS = {"wav", "mp3", "m4a", "flac", "ogg", "webm", "mp4"}

# Max file size: 25 MB (OpenAI limit)
MAX_FILE_SIZE = 25 * 1024 * 1024


class WhisperClient:
    """Client for whisper.cpp server with OpenAI-compatible API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.whisper_base_url,
                timeout=300.0,  # Transcription can take a while
            )
        return self._client

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        language: str | None = None,
        prompt: str | None = None,
        response_format: str = "json",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes.
            filename: Original filename (for format detection).
            language: ISO language code (e.g. "en"). None for auto-detect.
            prompt: Optional prompt to guide transcription.
            response_format: "json", "text", "srt", "verbose_json", "vtt".
            temperature: Sampling temperature.

        Returns:
            Transcription result dict with at minimum {"text": str}.
        """
        client = self._get_client()

        # Build multipart form data
        files = {"file": (filename, audio_data)}
        data: dict[str, Any] = {
            "response_format": response_format,
            "temperature": str(temperature),
        }
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt

        logger.info(
            "Whisper transcribe: file=%s, language=%s, format=%s",
            filename,
            language or "auto",
            response_format,
        )

        try:
            response = await client.post(
                "/inference",
                files=files,
                data=data,
            )
            response.raise_for_status()

            if response_format in ("text", "srt", "vtt"):
                return {"text": response.text}
            return response.json()

        except httpx.HTTPStatusError as exc:
            logger.error("Whisper HTTP error: %s", exc.response.text)
            raise
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Whisper server at {settings.whisper_base_url}. "
                "Is the whisper service running?"
            )

    async def translate(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        prompt: str | None = None,
        response_format: str = "json",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Translate audio to English text.

        Same as transcribe but forces English output regardless of source language.
        """
        return await self.transcribe(
            audio_data=audio_data,
            filename=filename,
            language="en",
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
        )

    async def batch_transcribe(
        self,
        audio_files: list[tuple[str, bytes]],
        language: str | None = None,
        response_format: str = "json",
    ) -> list[dict[str, Any]]:
        """
        Transcribe multiple audio files.

        Args:
            audio_files: List of (filename, audio_bytes) tuples.
            language: ISO language code or None for auto-detect.
            response_format: Output format.

        Returns:
            List of transcription results.
        """
        results = []
        for filename, audio_data in audio_files:
            try:
                result = await self.transcribe(
                    audio_data=audio_data,
                    filename=filename,
                    language=language,
                    response_format=response_format,
                )
                results.append({"filename": filename, "success": True, **result})
            except Exception as exc:
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": str(exc),
                })
        return results

    async def health_check(self) -> bool:
        """Check if the Whisper server is available."""
        try:
            client = self._get_client()
            response = await client.get("/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton
whisper_client = WhisperClient()
