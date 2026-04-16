"""Content domain: media pipelines (Whisper, captions, timelines)."""

from domain_content.whisper import WhisperError, WhisperRunResult, run_whisper_srt

__all__ = ["WhisperError", "WhisperRunResult", "run_whisper_srt", "default_content_pool_keys", "__version__"]

__version__ = "0.1.0"


def default_content_pool_keys() -> list[str]:
    """Return default knowledge pool keys for content workflows."""
    return ["video_editing"]
