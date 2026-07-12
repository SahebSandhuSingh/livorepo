"""
Pipeline Orchestrator — ties all processing steps together.

Step 1: Validate & convert audio
Step 2: Transcribe with Whisper (to get transcript & word timings)
Step 3: Run Azure Pronunciation Assessment (continuous recognition mode)
Step 4: Delete audio file (Cleanup)
Step 5: Flag low-scoring words and get plain-English feedback from OpenAI
Step 6: Build and return response
"""

import logging
import os

from fastapi import UploadFile

from app.config import get_settings
from app.models.schemas import AssessmentResponse, WordResult
from app.services import audio_validator, whisper_service, azure_pronunciation, openai_service

logger = logging.getLogger(__name__)


async def run_assessment(
    upload_file: UploadFile,
    threshold: int | None = None,
) -> AssessmentResponse:
    """
    End-to-end pronunciation assessment pipeline.

    Orchestrates validation → transcription → Azure assessment → OpenAI feedback → cleanup.
    Returns a complete AssessmentResponse, falling back gracefully if Azure fails.
    """
    settings = get_settings()
    flag_threshold = threshold if threshold is not None else settings.word_score_threshold
    wav_path: str | None = None

    # ------------------------------------------------------------------
    # Step 1 — Validate & Convert
    # ------------------------------------------------------------------
    wav_path, duration = await audio_validator.validate_and_convert(upload_file)
    logger.info("Step 1 complete: validated audio (%.1fs), WAV at %s", duration, wav_path)

    azure_result = None
    azure_error = ""

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
        # Step 4 — Delete the audio file immediately after Step 3
        # ------------------------------------------------------------------
        if wav_path:
            try:
                os.unlink(wav_path)
                logger.info("Step 4 complete: deleted temp audio %s", wav_path)
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

    logger.info("Azure assessment succeeded: accuracy=%.1f", azure_result.accuracy_score)

    # ------------------------------------------------------------------
    # Step 5 — Flag low-scoring words & generate OpenAI feedback
    # ------------------------------------------------------------------
    flagged_details = []
    
    for w in azure_result.words:
        if w.accuracy_score < flag_threshold or w.error_type in ["Mispronunciation", "Omission", "Insertion"]:
            # Format phoneme-level issues for OpenAI's context
            phoneme_errors = [
                f"{p.phoneme} ({p.issue})"
                for p in w.phonemes
                if p.issue not in ["None", ""]
            ]
            
            flagged_details.append({
                "word": w.word,
                "score": w.accuracy_score,
                "error_type": w.error_type,
                "phonemes_with_issues": phoneme_errors
            })

    logger.info("Flagged %d / %d words for OpenAI feedback", len(flagged_details), len(azure_result.words))

    # Fetch summary and per-word coaching tips from OpenAI
    openai_result = openai_service.generate_feedback(
        transcript=whisper_result.transcript,
        flagged_details=flagged_details
    )
    
    summary = openai_result.get("summary", "Pronunciation analyzed successfully.")
    word_feedback_map = openai_result.get("word_feedback", {})

    # Match key casing by converting to lowercase for checking
    normalized_feedback = {k.lower().strip(): v for k, v in word_feedback_map.items()}

    # ------------------------------------------------------------------
    # Step 6 — Build final response zipping Whisper times with Azure words
    # ------------------------------------------------------------------
    words_response: list[WordResult] = []

    for i, azure_word in enumerate(azure_result.words):
        # Match timing from Whisper based on index
        start = 0.0
        end = 0.0
        if i < len(whisper_result.words):
            start = whisper_result.words[i].start
            end = whisper_result.words[i].end

        # Identify issue type
        issue = azure_word.error_type if azure_word.error_type != "None" else ""
        
        # Get OpenAI feedback for flagged words
        clean_key = azure_word.word.lower().strip(".,?!;:")
        feedback_item = normalized_feedback.get(clean_key, {})
        
        # Check if the OpenAI service returned feedback
        feedback = ""
        if isinstance(feedback_item, dict):
            feedback = feedback_item.get("feedback", "")
            if not issue and feedback_item.get("issue"):
                issue = feedback_item.get("issue")
        elif isinstance(feedback_item, str):
            feedback = feedback_item

        # Fallback explanation if word was flagged but OpenAI didn't provide any text
        if not feedback and (azure_word.accuracy_score < flag_threshold or issue):
            feedback = f"Pronounced as {azure_word.error_type.lower()}."

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
        summary=summary,
        transcript=whisper_result.transcript,
        words=words_response,
        scoring_unavailable=False
    )

    return response
