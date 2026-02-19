import uuid
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from speech_to_text.processor import transcribe_audio
from speech_to_text.yarngpt_tts import synthesize_speech, YARNGPT_VOICES
from llm_providers import create_provider

load_dotenv()

llm_provider = create_provider()
chat_history: list[dict] = []


def _ask_llm(user_text: str) -> str:
    return llm_provider.ask(user_text, chat_history)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s"
)
log = logging.getLogger("monei")

AUDIO_DIR = Path("tmp_audio")
AUDIO_TTL = 300


def _cleanup_old_files():
    if not AUDIO_DIR.exists():
        return
    now = time.time()
    for f in AUDIO_DIR.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > AUDIO_TTL:
            f.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    AUDIO_DIR.mkdir(exist_ok=True)
    _cleanup_old_files()
    log.info("Monei Voice AI started")
    yield
    log.info("Shutting down")


app = FastAPI(title="Monei Voice AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice: str = Field(default="Idera")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/voices")
async def get_voices():
    return {
        "voices": [{"name": k, "description": v} for k, v in YARNGPT_VOICES.items()]
    }


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    ext = Path(audio.filename or "audio.webm").suffix or ".webm"
    file_id = uuid.uuid4().hex[:12]
    input_path = AUDIO_DIR / f"{file_id}{ext}"

    try:
        input_path.write_bytes(await audio.read())
        result = transcribe_audio(str(input_path), model_size="base")
        return {"text": result["text"], "language": result["language"]}
    except Exception as e:
        log.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _remove(input_path)
        _remove(input_path.with_name(f"{file_id}_converted.wav"))


@app.post("/api/chat")
async def chat_voice(audio: UploadFile = File(...), voice: str = Query("Idera")):
    ext = Path(audio.filename or "audio.webm").suffix or ".webm"
    file_id = uuid.uuid4().hex[:12]
    input_path = AUDIO_DIR / f"{file_id}{ext}"
    tts_path = AUDIO_DIR / f"{file_id}_response.mp3"

    try:
        input_path.write_bytes(await audio.read())
        log.info("STT started  id=%s", file_id)
        transcript = transcribe_audio(str(input_path), model_size="base")
        user_text = transcript["text"]
        log.info("STT done     id=%s  text=%s", file_id, user_text[:80])

        log.info("LLM started  id=%s", file_id)
        ai_response = _ask_llm(user_text)
        log.info("LLM done     id=%s  reply=%s", file_id, ai_response[:80])

        log.info("TTS started  id=%s  voice=%s", file_id, voice)
        synthesize_speech(
            text=ai_response,
            output_path=str(tts_path),
            voice=voice,
            response_format="mp3",
        )
        log.info("TTS done     id=%s", file_id)

        return {
            "user_text": user_text,
            "ai_text": ai_response,
            "audio_url": f"/api/audio/{file_id}_response.mp3",
        }
    except Exception as e:
        log.exception("Voice chat failed  id=%s", file_id)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _remove(input_path)
        _remove(input_path.with_name(f"{file_id}_converted.wav"))


@app.post("/api/chat/text")
async def chat_text(req: TextChatRequest):
    file_id = uuid.uuid4().hex[:12]
    tts_path = AUDIO_DIR / f"{file_id}_response.mp3"

    try:
        log.info("LLM started  id=%s", file_id)
        ai_response = _ask_llm(req.text)
        log.info("LLM done     id=%s  reply=%s", file_id, ai_response[:80])

        log.info("TTS started  id=%s  voice=%s", file_id, req.voice)
        synthesize_speech(
            text=ai_response,
            output_path=str(tts_path),
            voice=req.voice,
            response_format="mp3",
        )
        log.info("TTS done     id=%s", file_id)

        return {
            "user_text": req.text,
            "ai_text": ai_response,
            "audio_url": f"/api/audio/{file_id}_response.mp3",
        }
    except Exception as e:
        log.exception("Text chat failed  id=%s", file_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    path = AUDIO_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    _cleanup_old_files()
    return FileResponse(str(path), media_type="audio/mpeg")


def _remove(p: Path):
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


app.mount("/static", StaticFiles(directory="static"), name="static")
