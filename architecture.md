# Architecture & Trade-offs

## Speech Assessment Pipeline
1. **Audio Validation & Conversion**: Uploaded clips are validated and converted locally to 16kHz mono WAV format using static `ffmpeg`/`ffprobe` binaries.
2. **Transcription (Whisper)**: Audio is transcribed using `faster-whisper` on CPU with `int8` quantization.
3. **Pronunciation Scoring (Azure)**: The audio is sent to Azure Cognitive Services Continuous Speech Assessment API to retrieve word-level phoneme accuracy, fluency, completeness, and prosody scores.
4. **Coaching & Tips (OpenAI)**: Words with scores below the `WORD_SCORE_THRESHOLD` (default 80/100) are flagged and sent to OpenAI (`gpt-4o-mini`) using structured output to generate personalized, phoneme-specific coaching tips.

## Production Trade-offs & Resource Limits
* **Whisper Model Size**: The application is deployed to the Render Free Tier, which has a memory limit of 512MB RAM. During deployment, loading the `small.en` Whisper model (~480MB weights) exceeded the 512MB RAM limit and caused Out-of-Memory (OOM) crashes.
  * **Resolution**: Replaced `small.en` with the **`base.en`** model (~140MB weights, ~35MB under `int8` quantization). This comfortably runs within the 512MB limit, loading in ~100MB of RAM and leaving sufficient headroom for API operations and Azure Speech SDK allocations.
  * **Accuracy Impact**: The `base.en` model maintains high transcription accuracy for clear speech inputs while keeping memory footprint and transcription latency minimal.
