"""
Pipeline Orchestrator — ties all processing steps together.

Step 1: Validate & convert audio
Step 2: Transcribe with Whisper
Step 3: Azure pronunciation assessment
Step 4+5: Flag words & generate LLM feedback
Step 6: Delete audio file (in finally block after Step 3)
Step 7: Build and return response
"""

import logging
import os

from fastapi import UploadFile

from app.models.schemas import AssessmentResponse, WordResult
from app.services import audio_validator, whisper_service, azure_pronunciation, feedback_generator

logger = logging.getLogger(__name__)


async def run_assessment(
    upload_file: UploadFile,
    threshold: int | None = None,
) -> AssessmentResponse:
    """
    End-to-end pronunciation assessment pipeline.

    Orchestrates validation → transcription → scoring → feedback → cleanup.
    Returns a complete AssessmentResponse, falling back gracefully if Azure fails.
    """
    wav_path: str | None = None

    # ------------------------------------------------------------------
    # Step 1 — Validate & Convert
    # ------------------------------------------------------------------
    wav_path, duration = await audio_validator.validate_and_convert(upload_file)
    logger.info("Step 1 complete: validated audio (%.1fs), WAV at %s", duration, wav_path)

    try:
        # ------------------------------------------------------------------
        # Step 2 — Transcribe with Whisper
        # ------------------------------------------------------------------
        whisper_result = whisper_service.transcribe(wav_path)
        logger.info("Step 2 complete: transcript = '%s…' (%d words)",
                     whisper_result.transcript[:80], len(whisper_result.words))

        # ------------------------------------------------------------------
        # Step 3 — Azure Pronunciation Assessment
        # ------------------------------------------------------------------
        azure_result, azure_error = azure_pronunciation.assess(
            wav_path, whisper_result.transcript
        )

    finally:
        # ------------------------------------------------------------------
        # Step 6 — Delete the audio file immediately after Step 3
        # ------------------------------------------------------------------
        if wav_path:
            try:
                os.unlink(wav_path)
                logger.info("Step 6 complete: deleted temp audio %s", wav_path)
            except OSError as e:
                logger.warning("Failed to delete temp audio %s: %s", wav_path, e)

    # ------------------------------------------------------------------
    # Handle Azure failure → fallback response
    # ------------------------------------------------------------------
    if azure_result is None:
        logger.warning("Azure assessment unavailable: %s", azure_error)
        return AssessmentResponse(
            overall_score=0.0,
            fluency=0.0,
            completeness=0.0,
            prosody=0.0,
            summary=(
                "We were able to transcribe your audio, but pronunciation scoring "
                "is temporarily unavailable. Please try again later."
            ),
            transcript=whisper_result.transcript,
            words=[],
            scoring_unavailable=True,
            scoring_error=azure_error,
        )

    logger.info("Step 3 complete: Azure accuracy=%.1f", azure_result.accuracy_score)

    # ------------------------------------------------------------------
    # Steps 4+5 — Flag words & generate LLM feedback
    # ------------------------------------------------------------------
    flagged = feedback_generator.flag_words(azure_result, whisper_result, threshold=threshold)
    llm_feedback = feedback_generator.generate_feedback(
        flagged, whisper_result.transcript
    )
    logger.info("Steps 4+5 complete: %d flagged words, summary='%s…'",
                len(flagged), llm_feedback.summary[:60])

    # ------------------------------------------------------------------
    # Step 7 — Build final response
    # ------------------------------------------------------------------
    words_response: list[WordResult] = []

    for i, azure_word in enumerate(azure_result.words):
        # Get timing from Whisper (index-based merge)
        start = 0.0
        end = 0.0
        if i < len(whisper_result.words):
            start = whisper_result.words[i].start
            end = whisper_result.words[i].end

        # Get issue type
        issue = azure_word.error_type if azure_word.error_type != "None" else ""

        # Get LLM feedback (only for flagged words)
        feedback = llm_feedback.word_feedback.get(azure_word.word, "")

        words_response.append(WordResult(
            word=azure_word.word,
            start=start,
            end=end,
            score=azure_word.accuracy_score,
            issue=issue,
            feedback=feedback,
        ))

    response = AssessmentResponse(
        overall_score=azure_result.accuracy_score,
        fluency=azure_result.fluency_score,
        completeness=azure_result.completeness_score,
        prosody=azure_result.prosody_score,
        summary=llm_feedback.summary,
        transcript=whisper_result.transcript,
        words=words_response,
    )

    logger.info("Step 7 complete: response built with %d words", len(words_response))
    return response
