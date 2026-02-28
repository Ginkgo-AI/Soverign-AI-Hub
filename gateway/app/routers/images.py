"""Images router -- image generation and gallery endpoints.

Two routers are exported:
- ``generation_router`` for OpenAI-compatible /v1/images/generations
- ``gallery_router`` for /api/images gallery/serving endpoints
"""

import base64
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.middleware.auth import get_optional_user
from app.schemas.multimodal import (
    ImageGenData,
    ImageGenRequest,
    ImageGenResponse,
    ImageRecord,
)
from app.services.image_gen import image_gen_client, _parse_size

logger = logging.getLogger(__name__)

# OpenAI-compatible generation endpoint
generation_router = APIRouter()

# Gallery / serving endpoints
gallery_router = APIRouter()


@generation_router.post("/images/generations", response_model=ImageGenResponse)
async def create_image(
    request: ImageGenRequest,
    user=Depends(get_optional_user),
):
    """
    Generate images from a text prompt (OpenAI-compatible).

    Supports configurable parameters for Stable Diffusion: steps, CFG scale,
    size, seed, and optional LLM-powered prompt enhancement.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    width, height = _parse_size(request.size)

    # Optional: enhance prompt using LLM
    prompt = request.prompt
    revised_prompt = None
    if request.enhance_prompt:
        try:
            enhanced = await image_gen_client.enhance_prompt(prompt)
            if enhanced != prompt:
                revised_prompt = enhanced
                prompt = enhanced
        except Exception as exc:
            logger.warning("Prompt enhancement failed: %s", exc)

    try:
        images = await image_gen_client.generate(
            prompt=prompt,
            negative_prompt=request.negative_prompt,
            width=width,
            height=height,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            n=request.n,
            model=request.model,
        )

        # Format response
        data: list[ImageGenData] = []
        for img in images:
            item = ImageGenData(
                url=img.get("url"),
                revised_prompt=revised_prompt,
            )
            # If user requested b64_json, include the raw data
            if request.response_format == "b64_json" and img.get("filename"):
                filepath = Path("/data/files/generated") / img["filename"]
                if filepath.is_file():
                    item.b64_json = base64.b64encode(filepath.read_bytes()).decode("ascii")

            data.append(item)

        return ImageGenResponse(data=data)

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Image generation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}")


@gallery_router.get("/images", response_model=list[ImageRecord])
async def list_images(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_optional_user),
):
    """List generated images with pagination."""
    images = image_gen_client.list_images(limit=limit, offset=offset)
    return images


@gallery_router.get("/images/{image_id}")
async def get_image(
    image_id: str,
    user=Depends(get_optional_user),
):
    """Serve a generated image by ID."""
    result = image_gen_client.get_image(image_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_bytes, filename = result
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=86400",
        },
    )
