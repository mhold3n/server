"""Whisper CLI wrapper for caption generation (re-exports content domain)."""

from domain_content.whisper import WhisperError, WhisperRunResult, run_whisper_srt

__all__ = ["WhisperError", "WhisperRunResult", "run_whisper_srt"]
