"""
OpenAI Service — handles communication with OpenAI API using httpx.
Generates pronunciation feedback and aggregates sub-scores (fluency, completeness, prosody).
"""

import json
import logging
import httpx
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def generate_feedback(
    transcript: str,
    flagged_details: list[dict]
) -> dict:
    """
    Send the transcript and flagged low-confidence words (with phoneme details) to OpenAI to generate:
    1. A 1-2 sentence overall coaching summary.
    2. Plain-English coaching feedback for each flagged word.
    
    Args:
        transcript: The full text transcription.
        flagged_details: Low-confidence words with scores, errors, and phoneme details.
        
    Returns:
        A dict containing:
        - summary: A 1-2 sentence overall feedback summary.
        - word_feedback: A dictionary mapping word -> feedback string.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured. Returning fallback coaching.")
        return {
            "summary": "Pronunciation assessment complete. Please configure your OpenAI API key to get detailed AI coaching.",
            "word_feedback": {}
        }

    system_prompt = (
        "You are an expert English Pronunciation Coach. Your job is to analyze the student's speech "
        "and provide constructive, encouraging, plain-English coaching tips for flagged mispronounced words.\n\n"
        "You will be given:\n"
        "1. The full transcript of the audio.\n"
        "2. A list of words flagged with low scores (under 60/100) or pronunciation issues. Each flagged word contains "
        "its accuracy score, general error type, and a breakdown of phonemes that were mispronounced, substituted, or omitted.\n\n"
        "You must return a JSON object with the following fields:\n"
        "- summary: A 1-2 sentence summary of overall feedback and key advice based on their pronunciation.\n"
        "- word_feedback: A JSON object where keys are the exact flagged words (case-insensitive) and values are objects containing:\n"
        "    - issue: A string classification of the issue (e.g. 'Omission', 'Substitution', 'Mispronunciation', or 'Vowel sound').\n"
        "    - feedback: A short (10-15 words) coaching tip on how to say it better, referencing the specific phoneme error if applicable "
        "(e.g. 'Try extending the vowel sound slightly', or 'Make sure to touch your tongue to your palate for the D sound').\n\n"
        "Rules:\n"
        "- CRITICAL: You must generate a unique, specific coaching tip for every single flagged word individually. "
        "Never use the same generic copy-pasted feedback text for multiple different words.\n"
        "- Do not mention 'AI', 'confidence score', 'Whisper', 'Azure', or technical identifiers in your text. Address the student directly.\n"
        "- Only include the requested fields in the JSON. Return valid JSON only."
    )

    user_content = {
        "transcript": transcript,
        "flagged_words": flagged_details
    }

    try:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content)}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }

        logger.info("Sending request to OpenAI (%s) for feedback...", settings.openai_model)
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            raw_content = result["choices"][0]["message"]["content"]
            parsed_data = json.loads(raw_content)
            
            logger.info("Successfully received structured feedback from OpenAI.")
            return parsed_data

    except Exception as exc:
        logger.error("Failed to generate OpenAI feedback: %s", exc, exc_info=True)
        return {
            "summary": "Pronunciation analyzed. Try speaking at a steady pace and pronouncing each consonant clearly.",
            "word_feedback": {}
        }
