"""Merged JSON Schema registry for model-runtime + control-plane common (Draft 2020-12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
CP_DIR = REPO_ROOT / "schemas" / "control-plane" / "v1"
MR_DIR = REPO_ROOT / "schemas" / "model-runtime" / "v1"


def _load_registry(base: Path) -> dict[str, dict[str, Any]]:
    reg_path = base / "registry.json"
    manifest = json.loads(reg_path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for entry in manifest["schemas"]:
        data = json.loads((base / entry["path"]).read_text(encoding="utf-8"))
        out[data["$id"]] = data
    return out


def build_validator_store() -> dict[str, dict[str, Any]]:
    """All $id -> schema for RefResolver."""
    merged: dict[str, dict[str, Any]] = {}
    merged.update(_load_registry(CP_DIR))
    merged.update(_load_registry(MR_DIR))
    return merged
