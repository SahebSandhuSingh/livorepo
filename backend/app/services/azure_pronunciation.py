"""
Step 3 — Azure AI Speech Pronunciation Assessment.

Uses the Azure Speech SDK with continuous recognition to assess pronunciation
of audio files 30-45 seconds long. Returns per-word accuracy, phoneme-level
errors, and overall fluency/completeness/prosody scores.
"""

import json
import logging
import threading
from typing import Optional

import azure.cognitiveservices.speech as speechsdk

from app.config import get_settings
from app.models.schemas import AzureResult, AzureWordScore, PhonemeDetail

logger = logging.getLogger(__name__)


def assess(wav_path: str, reference_text: str) -> tuple[Optional[AzureResult], str]:
    """
    Run Azure pronunciation assessment on a WAV file.

    Uses continuous recognition since audio may exceed 30 seconds.

    Args:
        wav_path: Path to the WAV file (16kHz, mono, PCM 16-bit).
        reference_text: The reference transcript (from Whisper) to score against.

    Returns:
        Tuple of (AzureResult or None, error_message).
        On success: (AzureResult, "")
        On failure: (None, "human-readable error description")
    """
    settings = get_settings()

    if not settings.azure_speech_key:
        return None, "Azure Speech key not configured."

    try:
        return _run_assessment(wav_path, reference_text, settings)
    except Exception as exc:
        logger.error("Azure pronunciation assessment failed: %s", exc, exc_info=True)
        return None, f"Azure Speech API error: {exc}"


def _run_assessment(
    wav_path: str,
    reference_text: str,
    settings,
) -> tuple[Optional[AzureResult], str]:
    """Internal: run the actual assessment with continuous recognition."""

    # --- Configure speech service ---
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.azure_speech_key,
        region=settings.azure_speech_region,
    )
    speech_config.speech_recognition_language = "en-US"

    audio_config = speechsdk.AudioConfig(filename=wav_path)

    # --- Configure pronunciation assessment ---
    # EnableMiscue is not supported in continuous mode, so set to False.
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,
    )
    # Enable prosody scoring
    pronunciation_config.enable_prosody_assessment()

    # --- Create recognizer ---
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    pronunciation_config.apply_to(recognizer)

    # --- Collect results from continuous recognition ---
    done_event = threading.Event()
    all_results: list[dict] = []
    errors: list[str] = []

    def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        """Callback for each recognized utterance chunk."""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            try:
                pa_result = speechsdk.PronunciationAssessmentResult(evt.result)
                # Extract the detailed JSON for richer phoneme data
                detail_json = evt.result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult, "{}"
                )
                all_results.append({
                    "pa_result": pa_result,
                    "detail_json": json.loads(detail_json),
                })
            except Exception as e:
                logger.warning("Failed to parse pronunciation result: %s", e)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("Azure: NoMatch — speech could not be recognized.")

    def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        """Callback when recognition is canceled (error or end of stream)."""
        if evt.cancellation_details.reason == speechsdk.CancellationReason.Error:
            errors.append(
                f"Azure canceled with error: {evt.cancellation_details.error_details}"
            )
            logger.error("Azure recognition canceled: %s", evt.cancellation_details.error_details)
        done_event.set()

    def on_session_stopped(evt):
        """Callback when the session ends."""
        done_event.set()

    # Wire up callbacks
    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(on_session_stopped)

    # --- Start continuous recognition ---
    logger.info("Starting Azure pronunciation assessment (continuous mode)…")
    recognizer.start_continuous_recognition_async().get()

    # Wait for completion (timeout = 120s, generous for 30-45s audio)
    if not done_event.wait(timeout=120):
        recognizer.stop_continuous_recognition_async().get()
        return None, "Azure pronunciation assessment timed out after 120 seconds."

    recognizer.stop_continuous_recognition_async().get()

    # --- Check for errors ---
    if errors:
        return None, "; ".join(errors)

    if not all_results:
        return None, "Azure returned no recognition results for the audio."

    # --- Aggregate results across utterance chunks ---
    return _aggregate_results(all_results), ""


def _aggregate_results(all_results: list[dict]) -> AzureResult:
    """
    Aggregate pronunciation assessment results from multiple recognized chunks
    into a single AzureResult.
    """
    total_accuracy = 0.0
    total_fluency = 0.0
    total_completeness = 0.0
    total_prosody = 0.0
    chunk_count = len(all_results)

    all_words: list[AzureWordScore] = []

    for result_data in all_results:
        pa: speechsdk.PronunciationAssessmentResult = result_data["pa_result"]
        detail: dict = result_data["detail_json"]

        # Accumulate overall scores
        total_accuracy += pa.accuracy_score or 0.0
        total_fluency += pa.fluency_score or 0.0
        total_completeness += pa.completeness_score or 0.0
        total_prosody += pa.prosody_score or 0.0

        # Extract per-word scores from the detailed JSON
        nbest_list = detail.get("NBest", [{}])
        if nbest_list:
            nbest = nbest_list[0]
            for w in nbest.get("Words", []):
                pa_word = w.get("PronunciationAssessment", {})
                phonemes = []

                for p in w.get("Phonemes", []):
                    pa_phoneme = p.get("PronunciationAssessment", {})
                    phonemes.append(PhonemeDetail(
                        phoneme=p.get("Phoneme", ""),
                        score=pa_phoneme.get("AccuracyScore", 0.0),
                        issue=pa_phoneme.get("ErrorType", ""),
                    ))

                all_words.append(AzureWordScore(
                    word=w.get("Word", ""),
                    accuracy_score=pa_word.get("AccuracyScore", 0.0),
                    error_type=pa_word.get("ErrorType", "None"),
                    phonemes=phonemes,
                ))

    # Compute averages
    azure_result = AzureResult(
        accuracy_score=round(total_accuracy / chunk_count, 1) if chunk_count else 0.0,
        fluency_score=round(total_fluency / chunk_count, 1) if chunk_count else 0.0,
        completeness_score=round(total_completeness / chunk_count, 1) if chunk_count else 0.0,
        prosody_score=round(total_prosody / chunk_count, 1) if chunk_count else 0.0,
        words=all_words,
    )

    logger.info(
        "Azure assessment complete: accuracy=%.1f, fluency=%.1f, "
        "completeness=%.1f, prosody=%.1f, words=%d",
        azure_result.accuracy_score,
        azure_result.fluency_score,
        azure_result.completeness_score,
        azure_result.prosody_score,
        len(all_words),
    )

    return azure_result
