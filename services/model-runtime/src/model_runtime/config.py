"""Load models.yaml for resolved model_id strings (no duplicate IDs in code paths)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REL = Path(__file__).resolve().parents[2] / "config" / "models.yaml"


def load_models_config() -> dict[str, Any]:
    path = Path(os.environ.get("MODEL_RUNTIME_CONFIG_PATH", DEFAULT_REL))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolved_model_id(role: str) -> str:
    cfg = load_models_config()
    return str(cfg["models"][role]["model_id"])


def resolved_model_config(role: str) -> dict[str, Any]:
    cfg = load_models_config()
    model_cfg = cfg["models"][role]
    if not isinstance(model_cfg, dict):
        raise TypeError(f"models.{role} must be an object")
    return model_cfg
