# Monei Voice AI

A voice-mode AI web application. Speak into your microphone, get transcribed in real time, and hear an AI response spoken back to you.

## Stack

| Layer          | Technology                                |
| -------------- | ----------------------------------------- |
| Frontend       | Vanilla HTML / CSS / JS                   |
| Backend        | FastAPI (Python)                          |
| Speech-to-Text | OpenAI Whisper (local, free)              |
| Text-to-Speech | YarnGPT API (14 Nigerian-accented voices) |

## Project Structure

```
monei-task/
├── server.py                  # FastAPI application
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
├── .env                       # YARNGPT_API_KEY (not committed)
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

```
YARNGPT_API_KEY=sk_live_your_key_here
```

## Run

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

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

1. User presses the mic button and speaks
2. Browser records audio via MediaRecorder API (WebM/Opus)
3. Audio is uploaded to `/api/chat`
4. Server transcribes speech with Whisper (local, no API key)
5. Transcription is sent to the AI backend (Monei API — pending integration)
6. AI response text is synthesized to speech via YarnGPT
7. Audio response is streamed back and auto-played in the browser

## License

MIT
