"""
Step 1 — Audio Validation & Conversion.

Validates uploaded audio files for format, duration, and size.
Converts to WAV (PCM 16-bit, 16kHz, mono) for Azure Speech SDK compatibility.
"""

import logging
import tempfile
import os
from pathlib import Path

from fastapi import UploadFile, HTTPException
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Audio formats pydub can handle (via ffmpeg)
ALLOWED_CONTENT_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3",
    "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/ogg", "audio/flac", "audio/webm",
    "audio/aac",
    "audio/x-aac",
    # Some browsers send generic types
    "application/octet-stream",
}


async def validate_and_convert(upload: UploadFile) -> tuple[str, float]:
    """
    Validate the uploaded audio file and convert to Azure-compatible WAV.

    Returns:
        Tuple of (wav_file_path, duration_in_seconds).

    Raises:
        HTTPException: If the file fails validation (wrong type, bad duration,
        too large, or corrupt).
    """
    settings = get_settings()

    # ------------------------------------------------------------------
    # 1. Quick content-type pre-check
    # ------------------------------------------------------------------
    content_type = upload.content_type or ""
    if content_type and not (
        content_type.startswith("audio/")
        or content_type == "application/octet-stream"
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_file_type",
                "detail": (
                    f"Expected an audio file, got '{content_type}'. "
                    "Supported formats: WAV, MP3, M4A, OGG, FLAC, WebM, AAC."
                ),
            },
        )

    # ------------------------------------------------------------------
    # 2. Read into a temp file (respecting size limit)
    # ------------------------------------------------------------------
    raw_bytes = await upload.read()
    if len(raw_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "file_too_large",
                "detail": (
                    f"File size ({len(raw_bytes) / (1024*1024):.1f} MB) exceeds "
                    f"the {settings.max_upload_size_mb} MB limit."
                ),
            },
        )

    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "empty_file",
                "detail": "The uploaded file is empty.",
            },
        )

    # Write raw bytes to a temp file so pydub/ffmpeg can read it
    suffix = Path(upload.filename or "audio").suffix or ".wav"
    raw_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        raw_tmp.write(raw_bytes)
        raw_tmp.flush()
        raw_tmp.close()
    except Exception:
        _safe_delete(raw_tmp.name)
        raise

    # ------------------------------------------------------------------
    # 3. Load with pydub to validate it's actual audio
    # ------------------------------------------------------------------
    try:
        audio = AudioSegment.from_file(raw_tmp.name)
    except CouldntDecodeError:
        _safe_delete(raw_tmp.name)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_audio",
                "detail": (
                    "Could not decode the uploaded file as audio. "
                    "Please upload a valid audio file (WAV, MP3, M4A, OGG, FLAC)."
                ),
            },
        )
    except Exception as exc:
        _safe_delete(raw_tmp.name)
        logger.error("Unexpected error decoding audio: %s", exc)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "audio_decode_error",
                "detail": f"Failed to process audio file: {exc}",
            },
        )

    # ------------------------------------------------------------------
    # 4. Validate duration
    # ------------------------------------------------------------------
    duration_s = audio.duration_seconds
    if duration_s < settings.min_duration_s:
        _safe_delete(raw_tmp.name)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "audio_too_short",
                "detail": (
                    f"Audio duration is {duration_s:.1f}s. "
                    f"Minimum required is {settings.min_duration_s}s."
                ),
            },
        )
    if duration_s > settings.max_duration_s:
        _safe_delete(raw_tmp.name)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "audio_too_long",
                "detail": (
                    f"Audio duration is {duration_s:.1f}s. "
                    f"Maximum allowed is {settings.max_duration_s}s."
                ),
            },
        )

    # ------------------------------------------------------------------
    # 5. Convert to WAV: PCM 16-bit, 16 kHz, mono
    # ------------------------------------------------------------------
    wav_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    wav_path = wav_tmp.name
    wav_tmp.close()

    try:
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(wav_path, format="wav")
    except Exception as exc:
        _safe_delete(raw_tmp.name)
        _safe_delete(wav_path)
        logger.error("Failed to convert audio to WAV: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "conversion_failed",
                "detail": f"Failed to convert audio to WAV format: {exc}",
            },
        )

    # Clean up the original raw upload temp file
    _safe_delete(raw_tmp.name)

    logger.info(
        "Audio validated: duration=%.1fs, converted to WAV at %s",
        duration_s, wav_path,
    )
    return wav_path, duration_s


def _safe_delete(path: str) -> None:
    """Delete a file, ignoring errors if it doesn't exist."""
    try:
        os.unlink(path)
    except OSError:
        pass
