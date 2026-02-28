"""Audio router -- speech-to-text (Whisper) and text-to-speech (Piper) endpoints.

OpenAI-compatible audio API endpoints.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.middleware.auth import get_optional_user
from app.schemas.multimodal import AudioTranscription, TTSRequest
from app.services.tts import SUPPORTED_FORMATS as TTS_FORMATS
from app.services.tts import tts_client
from app.services.whisper import MAX_FILE_SIZE, SUPPORTED_FORMATS as AUDIO_FORMATS
from app.services.whisper import whisper_client

logger = logging.getLogger(__name__)
router = APIRouter()

# MIME type mapping for TTS output
_AUDIO_MIMES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "flac": "audio/flac",
}


# ---------------------------------------------------------------------------
# Speech-to-Text (Whisper)
# ---------------------------------------------------------------------------

@router.post("/audio/transcriptions", response_model=AudioTranscription)
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str | None = Form(None),
    prompt: str | None = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    user=Depends(get_optional_user),
):
    """
    Transcribe audio to text (OpenAI-compatible).

    Accepts audio file uploads in WAV, MP3, M4A, FLAC, OGG, WebM formats.
    """
    # Validate file extension
    filename = file.filename or "audio.wav"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext not in AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {ext}. Supported: {', '.join(sorted(AUDIO_FORMATS))}",
        )

    # Read file data
    audio_data = await file.read()
    if len(audio_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        result = await whisper_client.transcribe(
            audio_data=audio_data,
            filename=filename,
            language=language,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
        )

        # Handle different response formats
        if response_format in ("text", "srt", "vtt"):
            return Response(content=result.get("text", ""), media_type="text/plain")

        return AudioTranscription(
            text=result.get("text", ""),
            language=result.get("language"),
            duration=result.get("duration"),
            segments=result.get("segments"),
        )

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Transcription error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")


@router.post("/audio/translations", response_model=AudioTranscription)
async def create_translation(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    prompt: str | None = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    user=Depends(get_optional_user),
):
    """
    Translate audio to English text (OpenAI-compatible).

    Transcribes and translates audio from any supported language to English.
    """
    filename = file.filename or "audio.wav"
    audio_data = await file.read()

    if len(audio_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        result = await whisper_client.translate(
            audio_data=audio_data,
            filename=filename,
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
        )

        if response_format in ("text", "srt", "vtt"):
            return Response(content=result.get("text", ""), media_type="text/plain")

        return AudioTranscription(
            text=result.get("text", ""),
            language="en",
            duration=result.get("duration"),
            segments=result.get("segments"),
        )

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Translation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}")


# ---------------------------------------------------------------------------
# Text-to-Speech (Piper)
# ---------------------------------------------------------------------------

@router.post("/audio/speech")
async def create_speech(
    request: TTSRequest,
    user=Depends(get_optional_user),
):
    """
    Generate speech from text (OpenAI-compatible).

    Returns an audio stream in the requested format.
    """
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text is required")

    if request.response_format not in TTS_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {request.response_format}. Supported: {', '.join(sorted(TTS_FORMATS))}",
        )

    mime_type = _AUDIO_MIMES.get(request.response_format, "audio/wav")

    try:
        # Use streaming for longer texts
        if len(request.input) > 500:
            return StreamingResponse(
                tts_client.synthesize_stream(
                    text=request.input,
                    voice=request.voice,
                    response_format=request.response_format,
                    speed=request.speed,
                ),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'inline; filename="speech.{request.response_format}"',
                },
            )

        # Non-streaming for short texts
        audio_data = await tts_client.synthesize(
            text=request.input,
            voice=request.voice,
            response_format=request.response_format,
            speed=request.speed,
        )

        return Response(
            content=audio_data,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="speech.{request.response_format}"',
            },
        )

    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("TTS error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {exc}")
