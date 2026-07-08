"""
Steps 4+5 — Flag Low-Scoring Words & Generate LLM Feedback.

Identifies words below the score threshold, then sends ONLY the structured
flagged-word data (never raw audio) to Claude for plain-English explanations.
"""

import json
import logging
from typing import Optional

import anthropic

from app.config import get_settings
from app.models.schemas import (
    AzureResult,
    AzureWordScore,
    FlaggedWord,
    LLMFeedback,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)

# Tight system prompt — instructs Claude to explain scores, not invent them
SYSTEM_PROMPT = """\
You are a friendly, encouraging English pronunciation coach. You will receive a JSON array of words that a learner mispronounced, along with their pronunciation scores and phoneme-level error details.

Your job:
1. For each flagged word, write ONE short sentence (max 25 words) explaining what went wrong and how to fix it. Be specific — reference the actual phoneme or sound. Be encouraging, not critical.
2. Write a 1-2 sentence overall summary of the learner's pronunciation strengths and areas to improve.

Rules:
- Do NOT invent, alter, or re-interpret any scores. You only explain them.
- Do NOT reference technical terms like "phoneme" or "accuracy score" — use plain English.
- If a word has error_type "Omission", say the sound was dropped/skipped.
- If a word has error_type "Mispronunciation" or "Substitution", describe what sound was used instead.
- Keep feedback actionable: tell them what to DO, not just what went wrong.

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{
  "summary": "Overall summary here.",
  "word_feedback": {
    "word1": "Feedback for word1.",
    "word2": "Feedback for word2."
  }
}"""

# Generic fallbacks when Claude is unavailable
GENERIC_FEEDBACK = {
    "Mispronunciation": "This word wasn't quite right — try saying it slowly and clearly.",
    "Omission": "A sound was dropped in this word — try pronouncing each syllable.",
    "Insertion": "An extra sound was added — try to keep the pronunciation clean.",
    "None": "This word could use a bit more practice.",
}


def flag_words(
    azure_result: AzureResult,
    whisper_result: TranscriptionResult,
    threshold: Optional[int] = None,
) -> list[FlaggedWord]:
    """
    Identify words scoring below the threshold.

    Merges Azure per-word scores with Whisper timestamps.
    """
    settings = get_settings()
    threshold = threshold or settings.word_score_threshold

    # Build a lookup from Whisper words for timing info
    # Use a simple index-based merge (Azure and Whisper produce words in order)
    whisper_words = whisper_result.words
    flagged: list[FlaggedWord] = []

    for i, azure_word in enumerate(azure_result.words):
        if azure_word.accuracy_score >= threshold:
            continue

        # Try to match timing from Whisper (by index, fallback to 0.0)
        start_time = 0.0
        end_time = 0.0
        if i < len(whisper_words):
            start_time = whisper_words[i].start
            end_time = whisper_words[i].end

        flagged.append(FlaggedWord(
            word=azure_word.word,
            start_time=start_time,
            end_time=end_time,
            score=azure_word.accuracy_score,
            issue_type=azure_word.error_type,
            phoneme_detail=azure_word.phonemes,
        ))

    logger.info("Flagged %d/%d words below threshold %d",
                len(flagged), len(azure_result.words), threshold)
    return flagged


def generate_feedback(
    flagged_words: list[FlaggedWord],
    transcript: str,
) -> LLMFeedback:
    """
    Generate plain-English feedback for flagged words using Claude.

    If no words are flagged, returns a congratulatory summary without
    calling the LLM. If Claude fails, returns generic fallback feedback.
    """
    if not flagged_words:
        return LLMFeedback(
            summary="Excellent pronunciation! All words were clearly spoken.",
            word_feedback={},
        )

    settings = get_settings()

    if not settings.anthropic_api_key:
        logger.warning("Anthropic API key not configured — using generic feedback.")
        return _generic_fallback(flagged_words)

    try:
        return _call_claude(flagged_words, transcript, settings)
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc, exc_info=True)
        return _generic_fallback(flagged_words)


def _call_claude(
    flagged_words: list[FlaggedWord],
    transcript: str,
    settings,
) -> LLMFeedback:
    """Send flagged words to Claude and parse the structured response."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Build compact payload — only structured data, never raw audio
    payload = {
        "transcript": transcript,
        "flagged_words": [
            {
                "word": fw.word,
                "score": fw.score,
                "issue_type": fw.issue_type,
                "phoneme_detail": [
                    {"phoneme": p.phoneme, "score": p.score, "issue": p.issue}
                    for p in fw.phoneme_detail
                ],
            }
            for fw in flagged_words
        ],
    }

    logger.info("Sending %d flagged words to Claude for feedback…", len(flagged_words))

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": json.dumps(payload)},
        ],
    )

    # Parse Claude's response
    response_text = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the JSON
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    parsed = json.loads(response_text)

    return LLMFeedback(
        summary=parsed.get("summary", ""),
        word_feedback=parsed.get("word_feedback", {}),
    )


def _generic_fallback(flagged_words: list[FlaggedWord]) -> LLMFeedback:
    """Produce generic feedback when Claude is unavailable."""
    word_feedback = {}
    for fw in flagged_words:
        word_feedback[fw.word] = GENERIC_FEEDBACK.get(
            fw.issue_type, GENERIC_FEEDBACK["None"]
        )

    return LLMFeedback(
        summary=(
            f"Your pronunciation needs some work on {len(flagged_words)} "
            f"word{'s' if len(flagged_words) != 1 else ''}. "
            "Try practicing the flagged words slowly and clearly."
        ),
        word_feedback=word_feedback,
    )
