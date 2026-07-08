"""
POST /api/assess — Pronunciation Assessment endpoint.

Accepts a multipart audio upload and returns a complete pronunciation
assessment with word-level scores and feedback.
"""

import logging

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.models.schemas import AssessmentResponse, ErrorResponse
from app.services.pipeline import run_assessment

logger = logging.getLogger(__name__)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api", tags=["assessment"])


@router.post(
    "/assess",
    response_model=AssessmentResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Assess pronunciation of an audio clip",
    description=(
        "Upload a 30-45 second English audio clip (WAV, MP3, M4A, OGG, FLAC, WebM). "
        "Returns overall pronunciation scores and word-level feedback."
    ),
)
@limiter.limit(settings.rate_limit)
async def assess_pronunciation(
    request: Request,
    file: UploadFile = File(
        ...,
        description="Audio file (30-45 seconds, max 20 MB)",
    ),
    threshold: int | None = None,
):
    """
    Main assessment endpoint.

    Args:
        threshold: Optional override for the word-score flagging threshold
                   (0-100). Falls back to the FLAG_THRESHOLD env var (default 60).

    Pipeline:
    1. Validate audio (format, size, duration)
    2. Transcribe with Whisper
    3. Score pronunciation with Azure Speech
    4-5. Flag low-scoring words & generate LLM feedback
    6. Clean up temp files
    7. Return structured response
    """
    try:
        result = await run_assessment(file, threshold=threshold)
        return result

    except Exception as exc:
        # HTTPExceptions (from validation) are re-raised automatically by FastAPI.
        # This catches truly unexpected errors.
        logger.error("Unexpected error in /api/assess: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred. Please try again.",
            },
        )
