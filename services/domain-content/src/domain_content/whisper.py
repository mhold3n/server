"""Whisper CLI wrapper for caption generation (content domain).

This module intentionally calls the ``whisper`` command-line tool rather than embedding
model logic. That keeps the behavior deterministic and portable across planes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class WhisperError(RuntimeError):
    """Raised when whisper CLI invocation fails."""


@dataclass(frozen=True)
class WhisperRunResult:
    """Structured outcome from a whisper CLI run."""

    command: list[str]
    stdout: str
    stderr: str
    output_paths: list[str]


def run_whisper_srt(
    *,
    input_path: str,
    output_dir: str,
    language: str,
    model: str | None = None,
) -> WhisperRunResult:
    """Run whisper to generate SRT output for an input media file.

    Parameters
    ----------
    input_path
        Path to audio or video input.
    output_dir
        Directory for SRT output files.
    language
        Whisper language code.
    model
        Optional model name; falls back to ``MARTYMEDIA_WHISPER_MODEL`` or default CLI behavior.

    Returns
    -------
    WhisperRunResult
        Command echo and discovered ``.srt`` paths under ``output_dir``.

    Example
    -------
    >>> # run_whisper_srt(input_path="a.wav", output_dir="/tmp/out", language="en")  # doctest: +SKIP
    """
    if shutil.which("whisper") is None:
        raise WhisperError("whisper CLI not found on PATH")

    in_path = Path(input_path)
    if not in_path.exists():
        raise WhisperError(f"input does not exist: {input_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_model = model or os.environ.get("MARTYMEDIA_WHISPER_MODEL") or ""
    cmd = [
        "whisper",
        str(in_path),
        "--language",
        language,
        "--task",
        "transcribe",
        "--output_format",
        "srt",
        "--output_dir",
        str(out_dir),
    ]
    if resolved_model:
        cmd.extend(["--model", resolved_model])

    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise WhisperError(proc.stderr.strip() or f"whisper failed with {proc.returncode}")

    outputs = sorted(str(p) for p in out_dir.glob("*.srt"))
    return WhisperRunResult(command=cmd, stdout=proc.stdout, stderr=proc.stderr, output_paths=outputs)
