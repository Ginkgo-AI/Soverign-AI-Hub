"""Image Generation service -- text-to-image via ComfyUI / Stable Diffusion API.

Supports ComfyUI's API for Stable Diffusion image generation with configurable
parameters. Includes optional LLM prompt enhancement.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.llm import llm_backend

logger = logging.getLogger(__name__)

# Storage directory for generated images
GENERATED_DIR = Path("/data/files/generated")

# Image metadata store (in-memory; production should use DB)
_image_store: dict[str, dict[str, Any]] = {}


def _parse_size(size: str) -> tuple[int, int]:
    """Parse size string like '512x512' into (width, height)."""
    try:
        parts = size.lower().split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 512, 512


class ImageGenClient:
    """Client for ComfyUI / Stable Diffusion WebUI API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.comfyui_base_url,
                timeout=300.0,  # Image generation can be slow
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 30,
        cfg_scale: float = 7.0,
        seed: int = -1,
        n: int = 1,
        model: str = "",
    ) -> list[dict[str, Any]]:
        """
        Generate images from a text prompt.

        Args:
            prompt: Text description of desired image.
            negative_prompt: Things to avoid in the image.
            width: Image width in pixels.
            height: Image height in pixels.
            steps: Number of diffusion steps.
            cfg_scale: Classifier-free guidance scale.
            seed: Random seed (-1 for random).
            n: Number of images to generate.
            model: Checkpoint model name.

        Returns:
            List of dicts with image data and metadata.
        """
        client = self._get_client()

        # ComfyUI txt2img API payload
        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": seed if seed >= 0 else -1,
            "batch_size": n,
        }
        if model:
            payload["model"] = model

        logger.info(
            "Image gen: prompt=%s, size=%dx%d, steps=%d, n=%d",
            prompt[:80],
            width,
            height,
            steps,
            n,
        )

        try:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()

            # Store generated images to disk
            images = []
            image_list = result.get("images", [])
            if not image_list and result.get("image"):
                image_list = [result["image"]]

            for i, img_data in enumerate(image_list):
                image_id = uuid.uuid4().hex[:16]
                actual_seed = result.get("seed", seed)
                if isinstance(actual_seed, list):
                    actual_seed = actual_seed[i] if i < len(actual_seed) else seed

                image_info = await self._save_image(
                    image_data=img_data,
                    image_id=image_id,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=actual_seed,
                    model=model,
                )
                images.append(image_info)

            return images

        except httpx.HTTPStatusError as exc:
            logger.error("ComfyUI HTTP error: %s", exc.response.text)
            raise
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to ComfyUI at {settings.comfyui_base_url}. "
                "Is the comfyui service running?"
            )

    async def _save_image(
        self,
        image_data: str,
        image_id: str,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
        model: str,
    ) -> dict[str, Any]:
        """Save a generated image to disk and register metadata."""
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        filename = f"{image_id}.png"
        filepath = GENERATED_DIR / filename

        # Decode base64 image data
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[1]
        raw_bytes = base64.b64decode(image_data)
        filepath.write_bytes(raw_bytes)

        # Build metadata record
        record = {
            "id": image_id,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "filename": filename,
            "url": f"/api/images/{image_id}",
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": seed,
            "model": model,
            "created_at": datetime.utcnow().isoformat(),
            "file_size": len(raw_bytes),
        }
        _image_store[image_id] = record

        logger.info("Saved generated image: %s (%d bytes)", filename, len(raw_bytes))
        return record

    async def enhance_prompt(self, prompt: str, model: str = "", backend: str = "vllm") -> str:
        """
        Use an LLM to enhance a user prompt for better Stable Diffusion results.

        Rewrites a casual prompt into a detailed, SD-optimized description.
        """
        system_msg = (
            "You are a Stable Diffusion prompt engineer. Rewrite the user's image "
            "description into a detailed, high-quality Stable Diffusion prompt. "
            "Include style, lighting, composition details. Keep it under 200 words. "
            "Return ONLY the enhanced prompt, nothing else."
        )

        try:
            result = await llm_backend.chat_completion(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                backend=backend,
                temperature=0.7,
                max_tokens=256,
                stream=False,
            )
            enhanced = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return enhanced.strip() or prompt
        except Exception as exc:
            logger.warning("Prompt enhancement failed, using original: %s", exc)
            return prompt

    def get_image(self, image_id: str) -> tuple[bytes, str] | None:
        """
        Retrieve a generated image by ID.

        Returns:
            Tuple of (image_bytes, filename) or None if not found.
        """
        record = _image_store.get(image_id)
        if not record:
            return None

        filepath = GENERATED_DIR / record["filename"]
        if not filepath.is_file():
            return None

        return filepath.read_bytes(), record["filename"]

    def list_images(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List generated images with pagination."""
        all_images = sorted(
            _image_store.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
        return all_images[offset : offset + limit]

    def get_image_record(self, image_id: str) -> dict[str, Any] | None:
        """Get metadata for a generated image."""
        return _image_store.get(image_id)

    async def health_check(self) -> bool:
        """Check if the ComfyUI server is available."""
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
image_gen_client = ImageGenClient()
