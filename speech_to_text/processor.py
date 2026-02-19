"""
Processor module - Handles audio extraction and speech-to-text transcription.

Uses:
- moviepy/ffmpeg for extracting audio from video
- OpenAI Whisper (free, local) for speech-to-text
- pydub for audio format conversion (uses imageio-ffmpeg as fallback)
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional

from speech_to_text.collector import is_video, is_audio, ensure_dir


def _get_ffmpeg_path() -> str:
    """Get the path to ffmpeg, preferring system install, falling back to imageio-ffmpeg."""
    # Check system PATH first
    ffmpeg_sys = shutil.which("ffmpeg")
    if ffmpeg_sys:
        return ffmpeg_sys
    # Fall back to imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"  # Hope for the best


def _ensure_wav(audio_path: str) -> str:
    """
    Convert audio to WAV format if needed, so Whisper can read it without system ffmpeg.
    Returns path to a WAV file (may be the original if already WAV).
    """
    if audio_path.lower().endswith(".wav"):
        return audio_path

    import subprocess

    ffmpeg_path = _get_ffmpeg_path()
    wav_path = audio_path.rsplit(".", 1)[0] + "_converted.wav"
    print(f"  [Converting] {audio_path} -> WAV (via {os.path.basename(ffmpeg_path)})")

    cmd = [
        ffmpeg_path,
        "-y",  # overwrite output
        "-i",
        audio_path,  # input file
        "-ar",
        "16000",  # 16kHz sample rate
        "-ac",
        "1",  # mono
        "-f",
        "wav",  # WAV format
        wav_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [Warning] ffmpeg conversion failed: {result.stderr[:200]}")
        return audio_path  # Fall back to original

    return wav_path


def _load_audio_as_numpy(wav_path: str):
    """
    Load a WAV file as a float32 numpy array at 16kHz mono.
    This lets us bypass Whisper's internal ffmpeg call.
    """
    import numpy as np

    try:
        import scipy.io.wavfile as wavfile

        sr, data = wavfile.read(wav_path)
    except Exception:
        # Fallback: try soundfile
        import soundfile as sf

        data, sr = sf.read(wav_path)

    # Convert to float32 in [-1, 1]
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype != np.float32:
        data = data.astype(np.float32)

    # Convert stereo to mono
    if data.ndim > 1:
        data = data.mean(axis=1)

    # Resample to 16000 Hz if needed
    if sr != 16000:
        from scipy.signal import resample

        num_samples = int(len(data) * 16000 / sr)
        data = resample(data, num_samples).astype(np.float32)

    return data


def extract_audio_from_video(video_path: str, output_dir: str) -> str:
    """
    Extract audio track from a video file using moviepy.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save the extracted audio.

    Returns:
        Path to the extracted WAV audio file.
    """
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        raise ImportError("moviepy is required. Install: pip install moviepy")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    dest_dir = ensure_dir(output_dir)
    audio_filename = Path(video_path).stem + ".wav"
    audio_path = str(dest_dir / audio_filename)

    print(f"  [Extracting audio] {video_path} -> {audio_path}")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path, logger=None)
    clip.close()

    return audio_path


def transcribe_audio(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> dict:
    """
    Transcribe an audio file using OpenAI Whisper.

    Args:
        audio_path: Path to the audio file (wav, mp3, etc.).
        model_size: Whisper model size - 'tiny', 'base', 'small', 'medium', 'large'.
                    Smaller = faster, larger = more accurate.
        language: Optional language code (e.g., 'en', 'yo', 'ha').
                  Auto-detected if not specified.

    Returns:
        Dict with keys: 'text', 'segments', 'language', 'audio_path'
    """
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "openai-whisper is required. Install: pip install openai-whisper"
        )

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"  [Transcribing] {audio_path} (model: {model_size})")

    # Convert to WAV first to avoid ffmpeg dependency in Whisper
    wav_path = _ensure_wav(audio_path)

    # Load audio as numpy array ourselves
    audio_array = _load_audio_as_numpy(wav_path)

    model = whisper.load_model(model_size)

    options = {}
    if language:
        options["language"] = language

    # Pass numpy array directly instead of file path
    result = model.transcribe(audio_array, **options)

    transcription = {
        "audio_path": audio_path,
        "text": result["text"].strip(),
        "language": result.get("language", "unknown"),
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
    }

    print(
        f"  [Transcribed] Language: {transcription['language']}, "
        f"Length: {len(transcription['text'])} chars"
    )
    return transcription


def process_file(
    filepath: str,
    output_dir: str = "output",
    model_size: str = "base",
    language: Optional[str] = None,
) -> dict:
    """
    Process a single audio or video file end-to-end.

    For video files: extracts audio first, then transcribes.
    For audio files: transcribes directly.

    Args:
        filepath: Path to audio or video file.
        output_dir: Directory for intermediate and output files.
        model_size: Whisper model size.
        language: Optional language code.

    Returns:
        Transcription result dict.
    """
    audio_dir = os.path.join(output_dir, "extracted_audio")

    if is_video(filepath):
        audio_path = extract_audio_from_video(filepath, audio_dir)
    elif is_audio(filepath):
        audio_path = filepath
    else:
        raise ValueError(f"Unsupported file format: {filepath}")

    return transcribe_audio(audio_path, model_size=model_size, language=language)


def process_batch(
    filepaths: list[str],
    output_dir: str = "output",
    model_size: str = "base",
    language: Optional[str] = None,
) -> list[dict]:
    """
    Process multiple audio/video files.

    Args:
        filepaths: List of file paths to process.
        output_dir: Directory for outputs.
        model_size: Whisper model size.
        language: Optional language code.

    Returns:
        List of transcription results.
    """
    results = []
    for i, fp in enumerate(filepaths, 1):
        print(f"\n--- Processing file {i}/{len(filepaths)}: {fp} ---")
        try:
            result = process_file(fp, output_dir, model_size, language)
            results.append(result)
        except Exception as e:
            print(f"  [Error] Failed to process {fp}: {e}")
            results.append({"audio_path": fp, "error": str(e)})

    return results


def save_transcriptions(results: list[dict], output_path: str) -> str:
    """
    Save transcription results to a JSON file.

    Args:
        results: List of transcription dicts.
        output_path: Path to save the JSON file.

    Returns:
        Path to the saved file.
    """
    ensure_dir(str(Path(output_path).parent))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"  [Saved] Transcriptions -> {output_path}")
    return output_path
