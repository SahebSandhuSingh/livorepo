# System Architecture & Trade-offs

## 1. Components & Architecture

```
+---------------------------+       HTTPS POST       +------------------------------------+
|  Vite Frontend (Vercel)   |  ------------------->  |      FastAPI Backend (Render)      |
|  - React UI & Record      |  <-------------------  |  - Audio validation & conversion   |
|  - Waveform Playback      |    JSON Response       |  - Local timing / Azure API / LLM   |
+---------------------------+                        +------------------------------------+
                                                                    |         ^
                                                    Continuous      |         |  Acoustic
                                                    Acoustic Feed   v         |  Feedback
                                                     +------------------------------------+
                                                     |    Azure Speech Cognitive Service  |
                                                     |    (Deployed: Central India)       |
                                                     +------------------------------------+
```

### Flow Execution Sequence
1. **Frontend (Vercel)**: Collects microphone recording or audio upload, enforces explicit data privacy consent, validates parameters locally, and sends audio via HTTPS POST to the backend.
2. **Backend Orchestrator (Render)**: Receives file, checks duration constraints, normalizes format to WAV (16kHz, 16-bit mono PCM) via static `ffmpeg`/`ffprobe` binaries.
3. **Local ASR (faster-whisper)**: Transcribes the normalized WAV locally on CPU to align vocabulary and produce accurate word-level start/end timestamps.
4. **Pronunciation Assessor (Azure Speech SDK)**: Streams the WAV in continuous mode to compute phoneme-level, syllable, and word acoustic scores (accuracy, fluency, completeness).
5. **AI Coach (OpenAI GPT-4o-mini)**: Identifies words scoring below the `WORD_SCORE_THRESHOLD` (default 80) and calls GPT-4o-mini with structured schemas to generate phoneme-specific coaching tips.
6. **Response & Render**: Backend deletes the temporary WAV file and returns a structured JSON payload to the frontend for color-coded rendering and tooltip displaying.

---

## 2. Models & APIs Used, and Why

* **faster-whisper (base.en / int8)**: Chosen to produce accurate, word-level timestamps. Running a local, quantized model avoids external API billing/latency for transcription.
  * *Model size trade-off*: Downgraded from `small.en` to `base.en` to ensure CPU memory footprint fits comfortably within Render's Free Tier (512MB RAM ceiling).
* **Azure AI Speech API**: Chosen for acoustic scoring. Building a custom acoustic model for phoneme alignment from scratch was unfeasible under project time constraints. Faking scores with LLMs is structurally invalid since LLMs cannot inspect physical audio parameters.
* **OpenAI GPT-4o-mini**: Chosen for coaching tips. This step is a lightweight translation of structured error data (e.g., insertion, omission, score) into human-readable text. Using a larger model (like GPT-4) would introduce unnecessary cost and latency.
* **The Hybrid Whisper/Azure Pattern**: Combined because Azure’s continuous pronunciation assessment mode returns acoustic scores but does *not* return fine-grained word timestamps natively. Whisper computes the timeline alignment, while Azure computes acoustic precision.

---

## 3. Scoring & Highlighting Methodology

* **Pipeline**: Azure evaluates audio segments and returns per-word metrics (0-100) for *Accuracy* (phoneme match), *Fluency* (rhythm), and *Completeness* (omitted/inserted words).
* **Flagging Threshold**: Words scoring below `WORD_SCORE_THRESHOLD` (default: `80`) are marked as low-scoring. This value is fully configurable at the environment level.
* **LLM Explanation Generation**: The backend compiles flagged words, their scores, and error types (e.g. `Mispronunciation`, `Omission`) into a single prompt context. OpenAI generates unique coaching tips (e.g., advising on tongue position for a specific phoneme error) rather than copy-pasting generic labels.
* **Strict Separation of Concerns**: LLM judgment is **never** used to evaluate acoustic score. Scoring is computed purely by Azure's acoustic models; the LLM translation is restricted to generating human-readable coaching tips from the scored data.

---

## 4. DPDPA Compliance (India's Digital Personal Data Protection Act 2023)

* **Consent**: The user must explicitly tick an opt-in consent checkbox before recording or file upload buttons are enabled. Clear, plain-language text details the data processing lifecycle.
* **Storage**: No raw audio or audio metadata is persistently stored. The file is temporarily written to disk during execution and exists strictly in-memory or in ephemeral `/tmp` state.
* **Retention**: Ephemeral WAV files are deleted using explicit `try/finally` Python handlers immediately after the Azure assessment call returns, before LLM processing starts or the response is returned to the user.
* **Data Residency**: The Azure Speech cognitive resource is deployed specifically in the **Central India (Pune)** region. All voice-acoustic processing occurs strictly in-region.
* **Deletion Rights**: Because the pipeline is completely stateless and stores zero persistent user records or audio files, no user data remains on our servers to delete.
* **Production Grievance Officer**: Under the DPDPA, a production deployment would require registering a named Grievance Officer with an email contact in the terms/footer. This is noted as a requirement for full product release.

---

## 5. Production Readiness Notes

* **Current Free Tier Limitations**: Render's free instances spin down after inactivity, causing a **30-40 second cold-start delay** to boot the container and load Whisper weights.
* **Queuing & Load Balancing**: The API processes requests synchronously. In production, simultaneous uploads would block. A robust backend would employ request queuing (e.g., Celery + Redis) to handle jobs asynchronously.
* **Error Resilience & Fallback**: If Azure Speech is unavailable, the backend currently returns a warning. A production setup would degrade gracefully by showing transcript-only results.
* **Rate Limiting**: Rate limits are set to `5/minute` per IP using `slowapi` to protect backend capacity and control API billing costs.

---

## 6. Trade-Offs & Next Steps

* **Managed API vs. Custom Phoneme Alignment**: Using Azure Speech accelerates timeline delivery and guarantees high-quality phoneme assessment but introduces a third-party dependency.
* **Future Self-Hosted Roadmap (Next 1-2 Weeks)**:
  1. Migrate to a self-hosted `wav2vec2-based` phoneme scoring model to eliminate vendor dependency and ensure 100% data privacy.
  2. Implement playhead-synced word highlighting on the frontend during audio playback.
  3. Implement Redis-based request caching to prevent scoring identical audio files repeatedly.
