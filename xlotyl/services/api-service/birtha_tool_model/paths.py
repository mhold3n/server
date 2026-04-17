"""Resolve schema and registry paths relative to the vendored `xlotyl/` tree."""

from __future__ import annotations

import os
from pathlib import Path


def _xlotyl_root() -> Path:
    # birtha_tool_model -> api-service -> services -> xlotyl
    return Path(__file__).resolve().parents[3]


def schema_dir() -> Path:
    return _xlotyl_root() / "schemas" / "openclaw-bridge" / "v1"


def tool_model_schema_dir() -> Path:
    return schema_dir() / "tool-model"


def default_registry_path() -> Path:
    override = os.environ.get("BIRTHA_TOOL_MODEL_REGISTRY_PATH")
    if override:
        return Path(override)
    return schema_dir() / "registry.v1.json"
