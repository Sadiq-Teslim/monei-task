"""
YarnGPT Text-to-Speech module.

Uses the official YarnGPT API (https://yarngpt.ai/api/v1/tts) for generating
Nigerian-accented English and Nigerian language voices.

This module provides:
- Text-to-speech synthesis using YarnGPT's official API
- Multiple voice options (16 voices)
- MP3/WAV/OPUS/FLAC output formats
"""

import os
from pathlib import Path
from typing import Optional

from speech_to_text.collector import ensure_dir

YARNGPT_API_URL = "https://yarngpt.ai/api/v1/tts"

YARNGPT_VOICES = {
    "Idera": "Melodic, gentle",
    "Emma": "Authoritative, deep",
    "Zainab": "Soothing, gentle",
    "Osagie": "Smooth, calm",
    "Jude": "Warm, confident",
    "Chinenye": "Engaging, warm",
    "Tayo": "Upbeat, energetic",
    "Regina": "Mature, warm",
    "Adaora": "Warm, Engaging",
    "Umar": "Calm, smooth",
    "Mary": "Energetic, youthful",
    "Nonso": "Bold, resonant",
    "Remi": "Melodious, warm",
    "Adam": "Deep, Clear",
}


def _get_api_key() -> str:
    """
    Get YarnGPT API key from environment variable.

    Set via: YARNGPT_API_KEY=sk_live_...
    """
    key = os.environ.get("YARNGPT_API_KEY", "")
    if not key:
        raise ValueError(
            "YARNGPT_API_KEY environment variable not set. "
            "Get your API key from https://yarngpt.ai (Account Page) and set it:\n"
            "  set YARNGPT_API_KEY=sk_live_your_key_here"
        )
    return key


def synthesize_speech(
    text: str,
    output_path: str,
    voice: str = "Idera",
    response_format: str = "mp3",
    api_key: Optional[str] = None,
) -> str:
    """
    Generate speech from text using the official YarnGPT API.

    Args:
        text: The text to convert to speech. Max 2000 characters.
        output_path: Path to save the output audio file.
        voice: Voice character to use (default: 'Idera').
               See list_voices() for all options.
        response_format: Audio format - 'mp3', 'wav', 'opus', or 'flac'.
                         Default: 'mp3'.
        api_key: Optional API key override. If not provided, reads from
                 YARNGPT_API_KEY environment variable.

    Returns:
        Path to the generated audio file.

    Raises:
        ValueError: If text exceeds 2000 chars or voice is invalid.
        RuntimeError: If the API request fails.
    """
    import requests

    if len(text) > 2000:
        raise ValueError(f"Text too long ({len(text)} chars). Max is 2000 characters.")

    # Normalize voice name (capitalize first letter)
    voice = voice.strip().title()
    if voice not in YARNGPT_VOICES:
        available = ", ".join(YARNGPT_VOICES.keys())
        raise ValueError(f"Unknown voice '{voice}'. Available: {available}")

    if response_format not in ("mp3", "wav", "opus", "flac"):
        raise ValueError(
            f"Invalid format '{response_format}'. Use: mp3, wav, opus, flac"
        )

    key = api_key or _get_api_key()

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
        "voice": voice,
        "response_format": response_format,
    }

    print(f"  [YarnGPT] Voice: {voice} ({YARNGPT_VOICES[voice]})")
    print(f"  [YarnGPT] Format: {response_format}")
    print(f"  [YarnGPT] Text: {text[:80]}{'...' if len(text) > 80 else ''}")

    response = requests.post(YARNGPT_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        ensure_dir(str(Path(output_path).parent))
        with open(output_path, "wb") as f:
            f.write(response.content)
        size_kb = len(response.content) / 1024
        print(f"  [YarnGPT] Audio saved -> {output_path} ({size_kb:.1f} KB)")
        return output_path
    else:
        error_msg = response.text[:300]
        raise RuntimeError(
            f"YarnGPT API error (HTTP {response.status_code}): {error_msg}"
        )


def list_voices() -> dict[str, str]:
    """
    Return available YarnGPT voices with descriptions.

    Returns:
        Dict mapping voice names to descriptions.
    """
    return YARNGPT_VOICES.copy()


def list_voice_names() -> list[str]:
    """Return just the voice names."""
    return list(YARNGPT_VOICES.keys())


def batch_synthesize(
    texts: list[str],
    output_dir: str,
    voice: str = "Idera",
    response_format: str = "mp3",
    api_key: Optional[str] = None,
) -> list[str]:
    """
    Synthesize multiple texts to speech.

    Args:
        texts: List of text strings to synthesize.
        output_dir: Directory to save output files.
        voice: Voice to use for all texts.
        response_format: Audio format (mp3, wav, opus, flac).
        api_key: Optional API key override.

    Returns:
        List of paths to generated audio files.
    """
    output_paths = []

    for i, text in enumerate(texts, 1):
        output_path = os.path.join(output_dir, f"tts_output_{i:03d}.{response_format}")
        print(f"\n--- Synthesizing {i}/{len(texts)} ---")
        try:
            result = synthesize_speech(
                text,
                output_path,
                voice=voice,
                response_format=response_format,
                api_key=api_key,
            )
            output_paths.append(result)
        except Exception as e:
            print(f"  [Error] Failed to synthesize: {e}")
            output_paths.append(None)

    return output_paths
