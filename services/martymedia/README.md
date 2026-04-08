# MartyMedia Automation (services)

This service provides deterministic automation helpers intended to be callable from:
- the FastAPI control plane (`services/api`)
- agent-platform tools (`services/agent-platform/server`)
- DevPlane/OpenClaw workspaces

## Whisper captions

This service wraps the `whisper` CLI (OpenAI Whisper) to generate `.srt` caption files.

### Requirements

- Bootstrap the focused tool env from the repo root with `scripts/bootstrap_tool_env.sh whisper-asr`.
- `whisper` must be available on `PATH` inside the environment that runs this tool.
- `ffmpeg` is typically required by Whisper.

### CLI

Generate captions for a single media file:

```bash
martymedia-whisper --input "/path/to/video.mp4" --language en --output-dir "/path/to/out"
```

Environment variables:
- `MARTYMEDIA_WHISPER_MODEL` (optional): default Whisper model name to pass to `whisper --model`.
