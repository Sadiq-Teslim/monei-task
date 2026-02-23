# Monei Voice AI

A voice-mode AI web application. Speak into your microphone, get transcribed in real time, and hear an AI response spoken back to you.

## Stack

| Layer          | Technology                                       |
| -------------- | ------------------------------------------------ |
| Frontend       | Vanilla HTML / CSS / JS (dark theme, responsive) |
| Backend        | FastAPI (Python)                                 |
| LLM            | Monei API or Groq (env-switchable)               |
| Speech-to-Text | OpenAI Whisper (local, free)                     |
| Text-to-Speech | YarnGPT API (14 Nigerian-accented voices)        |

## Project Structure

```
monei-task/
├── server.py                  # FastAPI application
├── llm_providers.py           # LLM provider abstraction (Groq + Monei)
├── speech_to_text/
│   ├── __init__.py
│   ├── collector.py           # Audio/video file utilities
│   ├── processor.py           # Whisper STT engine
│   ├── yarngpt_tts.py         # YarnGPT TTS client
│   ├── pipeline.py            # Orchestrator (collect → transcribe → speak)
│   └── __main__.py            # CLI entry point
├── static/
│   ├── index.html             # App shell
│   ├── css/styles.css         # Styles & animations
│   └── js/app.js              # Client logic (mic, chat, audio playback)
├── build.sh                   # Render build script (CPU-only torch)
├── render.yaml                # Render deployment blueprint
├── .env                       # API keys & config (not committed)
├── requirements.txt
└── pyproject.toml
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux / Mac

pip install -r requirements.txt
```

Create a `.env` file:

```env
YARNGPT_API_KEY=sk_live_your_key_here
MONEI_API_KEY=mni_your_key_here
GROQ_API_KEY=gsk_your_key_here        # only needed if using Groq

# LLM provider: "monei" (default) or "groq"
LLM_PROVIDER=monei
```

## Run

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

## LLM Providers

The active LLM is controlled by the `LLM_PROVIDER` environment variable.

| Provider | Value   | Model                    | Notes                           |
| -------- | ------- | ------------------------ | ------------------------------- |
| Monei    | `monei` | Monei conversational API | Default. SSE streaming endpoint |
| Groq     | `groq`  | llama-3.3-70b-versatile  | Requires `groq` pip package     |

Switch providers by changing one line in `.env`:

```env
LLM_PROVIDER=groq
```

## API Endpoints

| Method | Path                | Description                                      |
| ------ | ------------------- | ------------------------------------------------ |
| `GET`  | `/`                 | Serve the web app                                |
| `GET`  | `/api/voices`       | List available TTS voices                        |
| `POST` | `/api/chat`         | Voice chat — upload audio, get AI audio response |
| `POST` | `/api/chat/text`    | Text chat — send text, get AI audio response     |
| `POST` | `/api/transcribe`   | Speech-to-text only                              |
| `GET`  | `/api/audio/{file}` | Serve generated audio files                      |

## How It Works

1. User presses the mic button (or types a message)
2. Browser records audio via MediaRecorder API (WebM/Opus)
3. Audio is uploaded to `/api/chat`
4. Server transcribes speech with Whisper (local, no API key needed)
5. Transcription is sent to the active LLM provider (Monei or Groq)
6. AI response text is synthesized to speech via YarnGPT
7. Audio response is streamed back and auto-played in the browser

## Deploy to Render

1. Push to GitHub
2. On [Render](https://dashboard.render.com), create a **New Blueprint** and connect the repo
3. Render reads `render.yaml` and prompts for the secret env vars
4. Minimum plan: **Standard** (2 GB RAM — required for Whisper + PyTorch)

## Deploy to Railway

1. Push to GitHub
2. Go to [Railway](https://railway.app) and click **New Project → Deploy from GitHub repo**
3. Select the `monei-task` repository
4. Railway auto-detects Python. Under **Settings**, set:
   - **Build Command:** `bash build.sh`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. Add environment variables under **Variables**:
   | Variable | Value |
   | --- | --- |
   | `LLM_PROVIDER` | `monei` |
   | `MONEI_API_KEY` | your Monei key |
   | `YARNGPT_API_KEY` | your YarnGPT key |
   | `GROQ_API_KEY` | your Groq key (optional) |
6. Click **Deploy** — Railway provisions the service and gives you a public URL
7. Minimum resource: **2 GB RAM** (Whisper + PyTorch requirement)

> **Tip:** Railway charges per usage. You can set a spending limit under **Settings → Usage** to avoid surprises.

## License

MIT
