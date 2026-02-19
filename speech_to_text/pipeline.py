"""
Main pipeline - Ties together collection, processing, and TTS synthesis.
"""

import os
import json
from typing import Optional

from speech_to_text.collector import (
    collect_local_file,
    collect_from_youtube,
    collect_from_directory,
    is_youtube_url,
    is_audio,
    is_video,
    ensure_dir,
)
from speech_to_text.processor import (
    process_file,
    process_batch,
    save_transcriptions,
)
from speech_to_text.yarngpt_tts import (
    synthesize_speech,
    batch_synthesize,
    list_voices,
    list_voice_names,
)


class SpeechPipeline:
    """
    End-to-end speech processing pipeline.

    Workflow:
        1. Collect audio/video from files, directories, or YouTube
        2. Process (extract audio from video + transcribe with Whisper)
        3. Optionally synthesize new speech with YarnGPT

    Example:
        pipeline = SpeechPipeline(output_dir="my_output")

        # Collect files
        pipeline.collect("path/to/audio.mp3")
        pipeline.collect("https://youtube.com/watch?v=...")
        pipeline.collect_directory("path/to/media/folder")

        # Transcribe all collected files
        results = pipeline.transcribe_all(model_size="base")

        # Generate speech from transcription
        pipeline.speak("Hello, this is YarnGPT speaking!", voice="Idera")
    """

    def __init__(self, output_dir: str = "output", whisper_model: str = "base"):
        self.output_dir = output_dir
        self.whisper_model = whisper_model
        self.collected_files: list[str] = []
        self.transcriptions: list[dict] = []

        # Create output subdirectories
        self.collect_dir = os.path.join(output_dir, "collected")
        self.audio_dir = os.path.join(output_dir, "extracted_audio")
        self.transcription_dir = os.path.join(output_dir, "transcriptions")
        self.tts_dir = os.path.join(output_dir, "tts_output")

        for d in [
            self.collect_dir,
            self.audio_dir,
            self.transcription_dir,
            self.tts_dir,
        ]:
            ensure_dir(d)

        print(f"Pipeline initialized. Output: {self.output_dir}")
        print(f"Whisper model: {self.whisper_model}")

    def collect(self, source: str, audio_only: bool = True) -> str:
        """
        Collect from a file path or YouTube URL.

        Args:
            source: Local file path or YouTube URL.
            audio_only: For YouTube, download audio only (default True).

        Returns:
            Path to the collected file.
        """
        print(f"\n=== Collecting: {source} ===")

        if is_youtube_url(source):
            filepath = collect_from_youtube(
                source, self.collect_dir, audio_only=audio_only
            )
        elif os.path.isfile(source):
            filepath = collect_local_file(source, self.collect_dir)
        else:
            raise ValueError(f"Invalid source: {source} (not a file or YouTube URL)")

        self.collected_files.append(filepath)
        return filepath

    def collect_directory(self, source_dir: str) -> list[str]:
        """
        Collect all audio/video files from a directory.

        Args:
            source_dir: Directory to scan.

        Returns:
            List of collected file paths.
        """
        print(f"\n=== Collecting from directory: {source_dir} ===")
        files = collect_from_directory(source_dir, self.collect_dir)
        self.collected_files.extend(files)
        return files

    def transcribe(self, filepath: str, language: Optional[str] = None) -> dict:
        """
        Transcribe a single file.

        Args:
            filepath: Path to audio or video file.
            language: Optional language code.

        Returns:
            Transcription result dict.
        """
        print(f"\n=== Transcribing: {filepath} ===")
        result = process_file(
            filepath,
            self.output_dir,
            model_size=self.whisper_model,
            language=language,
        )
        self.transcriptions.append(result)
        return result

    def transcribe_all(self, language: Optional[str] = None) -> list[dict]:
        """
        Transcribe all collected files.

        Args:
            language: Optional language code for all files.

        Returns:
            List of transcription results.
        """
        if not self.collected_files:
            print("No files collected yet. Use collect() first.")
            return []

        print(f"\n=== Transcribing {len(self.collected_files)} files ===")
        results = process_batch(
            self.collected_files,
            self.output_dir,
            model_size=self.whisper_model,
            language=language,
        )
        self.transcriptions.extend(results)

        # Save results
        output_path = os.path.join(self.transcription_dir, "transcriptions.json")
        save_transcriptions(results, output_path)

        return results

    def speak(
        self,
        text: str,
        voice: str = "Idera",
        filename: Optional[str] = None,
        response_format: str = "mp3",
    ) -> str:
        """
        Generate speech from text using YarnGPT API.

        Args:
            text: Text to speak (max 2000 chars).
            voice: YarnGPT voice name (default: 'Idera').
            filename: Output filename (auto-generated if not provided).
            response_format: Audio format - 'mp3', 'wav', 'opus', 'flac'.

        Returns:
            Path to the generated audio file.
        """
        if filename is None:
            existing = len(
                [
                    f
                    for f in os.listdir(self.tts_dir)
                    if f.endswith(f".{response_format}")
                ]
            )
            filename = f"speech_{existing + 1:03d}.{response_format}"

        output_path = os.path.join(self.tts_dir, filename)

        print(f"\n=== Generating speech with YarnGPT ===")
        return synthesize_speech(
            text, output_path, voice=voice, response_format=response_format
        )

    def speak_transcriptions(
        self,
        voice: str = "Idera",
        response_format: str = "mp3",
    ) -> list[str]:
        """
        Re-synthesize all transcriptions using YarnGPT.

        Args:
            voice: YarnGPT voice name.
            response_format: Audio format (mp3, wav, opus, flac).

        Returns:
            List of generated audio file paths.
        """
        texts = [t["text"] for t in self.transcriptions if "text" in t and t["text"]]
        if not texts:
            print("No transcriptions available. Run transcribe_all() first.")
            return []

        print(f"\n=== Synthesizing {len(texts)} transcriptions ===")
        return batch_synthesize(
            texts, self.tts_dir, voice=voice, response_format=response_format
        )

    def get_summary(self) -> dict:
        """Get a summary of the pipeline state."""
        return {
            "output_dir": self.output_dir,
            "whisper_model": self.whisper_model,
            "collected_files": len(self.collected_files),
            "transcriptions": len(self.transcriptions),
            "files": self.collected_files,
        }

    def __repr__(self):
        return (
            f"SpeechPipeline(output_dir='{self.output_dir}', "
            f"model='{self.whisper_model}', "
            f"files={len(self.collected_files)}, "
            f"transcriptions={len(self.transcriptions)})"
        )
