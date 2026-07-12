# Pronunciation Assessment API — Backend

FastAPI backend that accepts 30-45 second English audio clips and returns
pronunciation scores with word-level feedback.

## Pipeline

1. **Validate** — checks audio format, size (≤20 MB), duration (30-45s)
2. **Transcribe** — faster-whisper produces word-level timestamps + confidence
3. **Score** — Azure Speech SDK pronunciation assessment (continuous mode)
4. **Flag** — words scoring below threshold (default 80/100)
5. **Explain** — GPT-4o generates plain-English feedback per flagged word
6. **Cleanup** — temp audio deleted immediately after scoring
7. **Respond** — structured JSON with scores, transcript, and feedback

## Setup

```bash
# Prerequisites
brew install ffmpeg  # macOS — required by pydub & faster-whisper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## API

- `POST /api/assess` — Upload audio, receive assessment
- `GET /api/health` — Health check
- `GET /docs` — Interactive API documentation (Swagger)

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_SPEECH_KEY` | Yes | — | Azure Speech resource key |
| `AZURE_SPEECH_REGION` | No | `centralindia` | Azure region |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `WHISPER_MODEL` | No | `base.en` | Whisper model size |
| `WORD_SCORE_THRESHOLD` | No | `80` | Score below which words are flagged |
| `MAX_UPLOAD_SIZE_MB` | No | `20` | Maximum upload size |
| `RATE_LIMIT` | No | `5/minute` | Rate limit per IP |
