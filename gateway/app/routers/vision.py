"""Vision router -- image understanding and OCR endpoints."""

import base64
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.middleware.auth import get_optional_user
from app.schemas.multimodal import VisionRequest, VisionResponse
from app.services.vision import analyze_image, extract_text, validate_image_base64

logger = logging.getLogger(__name__)
router = APIRouter()

# Max image size: 20 MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024


async def _read_upload_as_base64(file: UploadFile) -> str:
    """Read an uploaded file and return as base64 data URI."""
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image file too large (max 20 MB)")

    mime = file.content_type or "image/jpeg"
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"


@router.post("/vision/analyze", response_model=VisionResponse)
async def vision_analyze(
    request: VisionRequest | None = None,
    image: UploadFile | None = File(None),
    prompt: str = Form("Describe this image in detail."),
    model: str = Form(""),
    user=Depends(get_optional_user),
):
    """
    Analyze an image with a text prompt.

    Accepts either:
    - JSON body with base64 images (VisionRequest)
    - Multipart form with uploaded image file + prompt
    """
    try:
        images: list[str] = []

        # JSON request with base64 images
        if request and request.images:
            for img in request.images:
                if not validate_image_base64(img):
                    raise HTTPException(status_code=400, detail="Invalid base64 image data")
            images = request.images
            prompt = request.prompt
            model = request.model

        # Multipart form upload
        elif image:
            images = [await _read_upload_as_base64(image)]

        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either images in JSON body or upload an image file",
            )

        backend = request.backend if request else "vllm"
        max_tokens = request.max_tokens if request else 1024
        temperature = request.temperature if request else 0.3
        stream = request.stream if request else False

        if stream:
            stream_iter = await analyze_image(
                images=images,
                prompt=prompt,
                model=model,
                backend=backend,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            return StreamingResponse(
                stream_iter,
                media_type="text/event-stream",
            )

        result = await analyze_image(
            images=images,
            prompt=prompt,
            model=model,
            backend=backend,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )

        # Extract content from OpenAI-format response
        content = ""
        usage = {}
        resp_model = model
        if isinstance(result, dict):
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            usage = result.get("usage", {})
            resp_model = result.get("model", model)

        return VisionResponse(content=content, model=resp_model, usage=usage)

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Vision analyze error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {exc}")


@router.post("/vision/extract", response_model=VisionResponse)
async def vision_extract(
    request: VisionRequest | None = None,
    image: UploadFile | None = File(None),
    model: str = Form(""),
    language: str | None = Form(None),
    user=Depends(get_optional_user),
):
    """
    Extract text (OCR) from an image.

    Accepts either:
    - JSON body with base64 images (VisionRequest)
    - Multipart form with uploaded image file
    """
    try:
        images: list[str] = []

        if request and request.images:
            for img in request.images:
                if not validate_image_base64(img):
                    raise HTTPException(status_code=400, detail="Invalid base64 image data")
            images = request.images
            model = request.model
        elif image:
            images = [await _read_upload_as_base64(image)]
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either images in JSON body or upload an image file",
            )

        backend = request.backend if request else "vllm"

        result = await extract_text(
            images=images,
            model=model,
            backend=backend,
            language_hint=language,
        )

        content = ""
        usage = {}
        resp_model = model
        if isinstance(result, dict):
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            usage = result.get("usage", {})
            resp_model = result.get("model", model)

        return VisionResponse(content=content, model=resp_model, usage=usage)

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Vision extract error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {exc}")
