"""Load and validate `birtha_bridge_tools` registry (class A / B / C)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from birtha_tool_model.paths import schema_dir, default_registry_path


def _registry_format_validator() -> Draft202012Validator:
    path = schema_dir() / "birtha_bridge_tools.v1.json"
    with path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    """Load `registry.v1.json` and validate against the registry format schema."""
    reg_path = default_registry_path()
    with reg_path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    _registry_format_validator().validate(data)
    return data


def tool_class(tool_name: str) -> str | None:
    """Return class letter ``A``, ``B``, or ``C`` for a registered tool, else ``None``."""
    reg = load_registry()
    for t in reg.get("tools", []):
        if t.get("name") == tool_name:
            return str(t["class"])
    return None


def assert_class_b(tool_name: str) -> tuple[bool, str | None]:
    """
    Return (ok, error_message).

    Class B may use the tool-model lane. Class A should stay local; class C is forbidden here.
    """
    cls = tool_class(tool_name)
    if cls is None:
        return False, "unknown_tool"
    if cls == "B":
        return True, None
    if cls == "A":
        return False, "tool_class_forbidden"
    if cls == "C":
        return False, "tool_class_forbidden"
    return False, "unknown_tool"
