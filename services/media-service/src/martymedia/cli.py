"""MartyMedia CLI entrypoints."""

from __future__ import annotations

import argparse
import json
import sys

from martymedia.whisper import WhisperError, run_whisper_srt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="martymedia-whisper")
    parser.add_argument("--input", required=True, help="Input media file path")
    parser.add_argument("--output-dir", required=True, help="Directory to write caption outputs")
    parser.add_argument("--language", required=True, choices=["en", "es"], help="Language code")
    parser.add_argument("--model", default=None, help="Optional whisper model override")
    args = parser.parse_args(argv)

    try:
        result = run_whisper_srt(
            input_path=args.input,
            output_dir=args.output_dir,
            language=args.language,
            model=args.model,
        )
    except WhisperError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "command": result.command,
                "output_paths": result.output_paths,
            },
            indent=2,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

