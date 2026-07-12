# AI Pronunciation Coach & Assessment Platform

A premium, full-stack web application designed to analyze spoken English audio and provide detailed, word-by-word pronunciation coaching. The project uses a hybrid local/cloud pipeline: local Whisper for precise timing alignment, Azure Speech Cognitive Services for continuous acoustic evaluation, and OpenAI GPT-4o-mini for personalized, phoneme-specific feedback.

---

## Key Features

* **Continuous Pronunciation Assessment**: Measures acoustic parameters (accuracy, fluency, completeness, and prosody) using Azure Speech SDK.
* **Local Timing Alignment**: Employs a quantized `faster-whisper` model (`base.en` running inside 100MB of RAM) to resolve word boundaries locally on the CPU.
* **Personalized AI Coaching**: Identifies words scoring below a threshold (default `80`) and generates targeted pronunciation tips via OpenAI.
* **DPDPA Compliance**: Incorporates explicit user consent checkbox, stateless processing (zero persistent audio storage), and geographic data residency (Central India region).
* **Premium Dashboard**: A clean, modern user interface featuring responsive dot-grid layout styling, custom SVG icons, and word-level score popover cards.

---

## Repository Structure

```text
├── backend/            # FastAPI Python backend application
│   ├── app/            # Main server routers, schemas, and pipelines
│   ├── bin/            # Local static ffmpeg/ffprobe binaries (built dynamically)
│   ├── build.sh        # Custom dependency installer and ffmpeg setup script
│   └── requirements.txt# Pinned Python package dependencies
├── frontend/           # React + Vite client application
│   ├── src/            # Components (UploadScreen, ResultsScreen, LoadingScreen)
│   └── index.html      # Main HTML entry point
├── render.yaml         # Render Blueprint Infrastructure-as-Code (IaC) file
├── vercel.json         # Vercel deployment configuration
├── architecture.md     # In-depth architectural design and trade-offs
└── README.md           # This project overview document
```

---

## Local Development Setup

### 1. Backend Setup

1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a Python 3.11 virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create your local environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your actual credentials (`AZURE_SPEECH_KEY`, `OPENAI_API_KEY`).
5. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### 2. Frontend Setup

1. Navigate to the frontend folder:
   ```bash
   cd ../frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Create your local environment file:
   ```bash
   cp .env.example .env
   ```
   Make sure it points to your local backend API:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
4. Start the frontend Vite development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## Environment Variables

### Backend Configuration (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_SPEECH_KEY` | **Yes** | — | Azure Cognitive Services Speech API Key |
| `AZURE_SPEECH_REGION` | **Yes** | `centralindia` | Azure Resource Region |
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API Authentication Key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | ChatGPT completions model version |
| `WORD_SCORE_THRESHOLD` | No | `80` | Score threshold below which words are flagged |
| `ALLOWED_ORIGINS` | No | *(Local)* | Comma-separated list of allowed frontend origins |
| `PYTHON_VERSION` | No | `3.11.9` | Enforced Python environment version |
| `WHISPER_MODEL` | No | `base.en` | ASR model size (`base.en` optimized for 512MB RAM) |

### Frontend Configuration (`frontend/.env`)

* **`VITE_API_BASE_URL`**: HTTP address of your live backend (e.g. `https://your-backend.onrender.com`).

---

## Deployed Status

* **Backend**: Deployed to **Render** under Python 3.11 with custom static ffmpeg binaries.
* **Frontend**: Deployed to **Vercel** with Vite production optimizations.