"""Repo-level schema compile gates (control-plane + model-runtime)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_control_plane_schema_gate() -> None:
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "validate_control_plane_schemas.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_model_runtime_schema_gate() -> None:
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "validate_model_runtime_schemas.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
