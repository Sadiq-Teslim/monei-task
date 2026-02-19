"""
Collector module - Handles collecting audio and video from various sources.

Supports:
- Local audio files (wav, mp3, flac, ogg, m4a)
- Local video files (mp4, mkv, avi, mov, webm)
- YouTube URLs (via yt-dlp)
"""

import os
import shutil
from pathlib import Path
from typing import Optional

# Supported formats
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"}


def ensure_dir(path: str) -> Path:
    """Create directory if it doesn't exist."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_audio(filepath: str) -> bool:
    """Check if a file is a supported audio format."""
    return Path(filepath).suffix.lower() in AUDIO_EXTENSIONS


def is_video(filepath: str) -> bool:
    """Check if a file is a supported video format."""
    return Path(filepath).suffix.lower() in VIDEO_EXTENSIONS


def is_youtube_url(url: str) -> bool:
    """Check if a string looks like a YouTube URL."""
    return any(
        domain in url for domain in ["youtube.com", "youtu.be", "youtube-nocookie.com"]
    )


def collect_local_file(filepath: str, output_dir: str) -> str:
    """
    Copy a local audio or video file to the output directory.

    Args:
        filepath: Path to the source file.
        output_dir: Directory to copy the file into.

    Returns:
        Path to the copied file.

    Raises:
        FileNotFoundError: If the source file doesn't exist.
        ValueError: If the file format is not supported.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    if not (is_audio(filepath) or is_video(filepath)):
        raise ValueError(
            f"Unsupported format: {Path(filepath).suffix}. "
            f"Supported: {AUDIO_EXTENSIONS | VIDEO_EXTENSIONS}"
        )

    dest_dir = ensure_dir(output_dir)
    dest_path = dest_dir / Path(filepath).name

    shutil.copy2(filepath, dest_path)
    print(f"  [Collected] {filepath} -> {dest_path}")
    return str(dest_path)


def collect_from_youtube(url: str, output_dir: str, audio_only: bool = True) -> str:
    """
    Download audio/video from YouTube using yt-dlp.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save the downloaded file.
        audio_only: If True, extract audio only (default). Otherwise download video.

    Returns:
        Path to the downloaded file.
    """
    try:
        import yt_dlp
    except ImportError:
        raise ImportError(
            "yt-dlp is required to download from YouTube. Install: pip install yt-dlp"
        )

    dest_dir = ensure_dir(output_dir)

    if audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
            "quiet": True,
        }
    else:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
            "quiet": True,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "unknown")

        if audio_only:
            output_file = str(dest_dir / f"{title}.wav")
        else:
            output_file = str(dest_dir / f"{title}.mp4")

        print(f"  [Downloaded] {url} -> {output_file}")
        return output_file


def collect_from_directory(source_dir: str, output_dir: str) -> list[str]:
    """
    Scan a directory and collect all supported audio/video files.

    Args:
        source_dir: Directory to scan.
        output_dir: Directory to copy collected files into.

    Returns:
        List of paths to collected files.
    """
    if not os.path.isdir(source_dir):
        raise NotADirectoryError(f"Not a directory: {source_dir}")

    collected = []
    for root, _, files in os.walk(source_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if is_audio(fpath) or is_video(fpath):
                try:
                    result = collect_local_file(fpath, output_dir)
                    collected.append(result)
                except Exception as e:
                    print(f"  [Warning] Skipping {fpath}: {e}")

    print(f"  [Summary] Collected {len(collected)} files from {source_dir}")
    return collected
