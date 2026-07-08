"""
Step 2 — Whisper Transcription Service.

Uses faster-whisper to produce a full transcript with word-level timestamps
and per-word confidence scores.
"""

import logging
from faster_whisper import WhisperModel

from app.config import get_settings
from app.models.schemas import TranscriptionResult, WhisperWord

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once at import / startup
_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    """Lazy-load and cache the Whisper model."""
    global _model
    if _model is None:
        settings = get_settings()
        logger.info("Loading Whisper model '%s' (this may take a moment)…", settings.whisper_model)
        _model = WhisperModel(
            settings.whisper_model,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper model loaded successfully.")
    return _model


def preload_model() -> None:
    """Pre-load the model at app startup so the first request isn't slow."""
    get_model()


def transcribe(audio_path: str) -> TranscriptionResult:
    """
    Transcribe an audio file and return word-level results.

    Args:
        audio_path: Path to a WAV audio file.

    Returns:
        TranscriptionResult with full transcript and per-word details.
    """
    model = get_model()

    logger.info("Transcribing audio: %s", audio_path)
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
    )

    all_words: list[WhisperWord] = []
    transcript_parts: list[str] = []

    for segment in segments:
        transcript_parts.append(segment.text.strip())

        if segment.words:
            for w in segment.words:
                all_words.append(
                    WhisperWord(
                        word=w.word.strip(),
                        start=round(w.start, 3),
                        end=round(w.end, 3),
                        probability=round(w.probability, 4),
                    )
                )

    full_transcript = " ".join(transcript_parts)

    logger.info(
        "Transcription complete: %d words, language=%s (prob=%.2f)",
        len(all_words),
        info.language,
        info.language_probability,
    )

    return TranscriptionResult(
        transcript=full_transcript,
        words=all_words,
    )
