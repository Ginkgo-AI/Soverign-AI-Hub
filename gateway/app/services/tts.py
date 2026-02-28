"""Text-to-Speech service -- audio synthesis via Piper TTS HTTP server.

Piper is a fast, local neural TTS engine. This client communicates with
the Piper HTTP server to synthesize speech from text.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Supported output formats
SUPPORTED_FORMATS = {"wav", "mp3", "opus", "flac"}

# Voice mapping (user-friendly name -> piper voice ID)
DEFAULT_VOICES: dict[str, str] = {
    "default": "en_US-lessac-medium",
    "alloy": "en_US-lessac-medium",
    "echo": "en_US-ryan-medium",
    "fable": "en_GB-alan-medium",
    "onyx": "en_US-ryan-low",
    "nova": "en_US-amy-medium",
    "shimmer": "en_US-lessac-high",
}


class PiperTTSClient:
    """Client for Piper TTS HTTP server."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.piper_base_url,
                timeout=120.0,
            )
        return self._client

    def _resolve_voice(self, voice: str) -> str:
        """Resolve a friendly voice name to a Piper voice ID."""
        return DEFAULT_VOICES.get(voice.lower(), voice)

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        response_format: str = "wav",
        speed: float = 1.0,
    ) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: Input text to speak.
            voice: Voice name or Piper voice ID.
            response_format: Output audio format.
            speed: Speech rate multiplier (0.25 to 4.0).

        Returns:
            Raw audio bytes in the requested format.
        """
        client = self._get_client()
        piper_voice = self._resolve_voice(voice)

        logger.info(
            "TTS synthesize: voice=%s, format=%s, speed=%.1f, text_len=%d",
            piper_voice,
            response_format,
            speed,
            len(text),
        )

        # Piper HTTP API endpoint
        params: dict[str, Any] = {
            "text": text,
            "voice": piper_voice,
            "speed": speed,
        }
        if response_format != "wav":
            params["output_format"] = response_format

        try:
            response = await client.post("/api/tts", json=params)
            response.raise_for_status()
            return response.content

        except httpx.HTTPStatusError as exc:
            logger.error("Piper TTS HTTP error: %s", exc.response.text)
            raise
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Piper TTS server at {settings.piper_base_url}. "
                "Is the piper service running?"
            )

    async def synthesize_stream(
        self,
        text: str,
        voice: str = "default",
        response_format: str = "wav",
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """
        Synthesize speech and stream audio chunks.

        Yields audio data in chunks for progressive playback.
        """
        client = self._get_client()
        piper_voice = self._resolve_voice(voice)

        params: dict[str, Any] = {
            "text": text,
            "voice": piper_voice,
            "speed": speed,
        }
        if response_format != "wav":
            params["output_format"] = response_format

        try:
            async with client.stream("POST", "/api/tts", json=params) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    yield chunk

        except httpx.HTTPStatusError as exc:
            logger.error("Piper TTS stream error: %s", exc.response.text)
            raise
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Piper TTS server at {settings.piper_base_url}. "
                "Is the piper service running?"
            )

    async def list_voices(self) -> list[dict[str, Any]]:
        """List available Piper voices."""
        client = self._get_client()
        try:
            response = await client.get("/api/voices")
            response.raise_for_status()
            return response.json()
        except Exception:
            # Return default voice list if server doesn't support listing
            return [
                {"id": v, "name": k}
                for k, v in DEFAULT_VOICES.items()
            ]

    async def health_check(self) -> bool:
        """Check if the Piper TTS server is available."""
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
tts_client = PiperTTSClient()
