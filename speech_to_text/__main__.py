"""
CLI entry point for the Speech-to-Text pipeline.

Usage:
    python -m speech_to_text transcribe <file_or_url> [options]
    python -m speech_to_text collect <source> [options]
    python -m speech_to_text speak <text> [options]
    python -m speech_to_text voices
"""

import argparse
import sys
import json

from speech_to_text.pipeline import SpeechPipeline
from speech_to_text.yarngpt_tts import list_voices


def main():
    parser = argparse.ArgumentParser(
        prog="speech_to_text",
        description="Speech-to-Text pipeline with YarnGPT TTS",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- transcribe command ---
    transcribe_parser = subparsers.add_parser(
        "transcribe", help="Transcribe audio/video files to text"
    )
    transcribe_parser.add_argument(
        "sources", nargs="+", help="File paths or YouTube URLs to transcribe"
    )
    transcribe_parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    transcribe_parser.add_argument(
        "--language",
        default=None,
        help="Language code (e.g., en, yo, ha). Auto-detected if omitted.",
    )
    transcribe_parser.add_argument(
        "--output-dir", default="output", help="Output directory (default: output)"
    )
    transcribe_parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    # --- collect command ---
    collect_parser = subparsers.add_parser(
        "collect", help="Collect audio/video files without transcribing"
    )
    collect_parser.add_argument(
        "sources", nargs="+", help="File paths, directories, or YouTube URLs"
    )
    collect_parser.add_argument(
        "--output-dir", default="output", help="Output directory (default: output)"
    )
    collect_parser.add_argument(
        "--video",
        action="store_true",
        help="For YouTube: download video instead of audio only",
    )

    # --- speak command ---
    speak_parser = subparsers.add_parser(
        "speak", help="Generate speech from text using YarnGPT"
    )
    speak_parser.add_argument("text", help="Text to convert to speech (max 2000 chars)")
    speak_parser.add_argument(
        "--voice",
        default="Idera",
        help="Voice name (default: Idera). Use 'voices' command to list all.",
    )
    speak_parser.add_argument(
        "--format",
        default="mp3",
        choices=["mp3", "wav", "opus", "flac"],
        help="Audio output format (default: mp3)",
    )
    speak_parser.add_argument("--output", default=None, help="Output file path")
    speak_parser.add_argument(
        "--output-dir", default="output", help="Output directory (default: output)"
    )

    # --- voices command ---
    subparsers.add_parser("voices", help="List available YarnGPT voices")

    # Parse and dispatch
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "voices":
        print("Available YarnGPT voices:")
        for name, desc in list_voices().items():
            print(f"  {name:12s} - {desc}")
        return

    if args.command == "transcribe":
        pipeline = SpeechPipeline(output_dir=args.output_dir, whisper_model=args.model)
        for source in args.sources:
            pipeline.collect(source)

        results = pipeline.transcribe_all(language=args.language)

        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                if "error" in r:
                    print(f"\n[ERROR] {r['audio_path']}: {r['error']}")
                else:
                    print(f"\n--- {r['audio_path']} ---")
                    print(f"Language: {r['language']}")
                    print(f"Text: {r['text']}")

    elif args.command == "collect":
        pipeline = SpeechPipeline(output_dir=args.output_dir)
        for source in args.sources:
            import os

            if os.path.isdir(source):
                pipeline.collect_directory(source)
            else:
                pipeline.collect(source, audio_only=not args.video)

        summary = pipeline.get_summary()
        print(f"\nCollected {summary['collected_files']} files.")

    elif args.command == "speak":
        pipeline = SpeechPipeline(output_dir=args.output_dir)
        result = pipeline.speak(
            args.text,
            voice=args.voice,
            filename=args.output,
            response_format=args.format,
        )
        print(f"\nGenerated: {result}")


if __name__ == "__main__":
    main()
