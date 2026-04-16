"""JSON Schema validation plus attachment byte limits for ``openclaw_bridge`` envelopes.

For agents: schema files live under repo ``schemas/openclaw-bridge/v1/``. The API
image copies ``schemas/`` adjacent to ``src/`` (see ``services/api-service/Dockerfile``);
this module walks upward from ``__file__`` until it finds
``schemas/openclaw-bridge/v1/openclaw-bridge-envelope.schema.json``.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import structlog
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

logger = structlog.get_logger(__name__)

DEFAULT_MAX_INLINE_ATTACHMENT_BYTES = 65_536

_ENVELOPE_SCHEMA_PATH = "schemas/openclaw-bridge/v1/openclaw-bridge-envelope.schema.json"


class OpenClawBridgeValidationError(Exception):
    """Raised when ``context.openclaw_bridge`` fails schema or attachment policy."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _find_envelope_schema_path() -> Path:
    """Resolve schema path for monorepo, ``xlotyl/schemas/``, and Docker ``/app/schemas`` layouts."""
    here = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    for start in (cwd, *cwd.parents, here.parent, *here.parents):
        for prefix in ("xlotyl/schemas", "schemas"):
            candidate = start / prefix / "openclaw-bridge/v1/openclaw-bridge-envelope.schema.json"
            if candidate.is_file():
                return candidate
        candidate = start / _ENVELOPE_SCHEMA_PATH
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"Could not locate {_ENVELOPE_SCHEMA_PATH} from {here}")


def _load_envelope_validator() -> Draft202012Validator:
    path = _find_envelope_schema_path()
    with path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


_ENVELOPE_VALIDATOR = None


def _validator() -> Draft202012Validator:
    global _ENVELOPE_VALIDATOR
    if _ENVELOPE_VALIDATOR is None:
        _ENVELOPE_VALIDATOR = _load_envelope_validator()
    return _ENVELOPE_VALIDATOR


def _total_inline_attachment_bytes(bridge: dict[str, Any]) -> int:
    total = 0
    attachments = bridge.get("attachments")
    if not isinstance(attachments, list):
        return 0
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "inline_base64":
            continue
        raw = item.get("data")
        if not isinstance(raw, str):
            continue
        try:
            total += len(base64.b64decode(raw, validate=True))
        except (ValueError, TypeError) as exc:
            raise OpenClawBridgeValidationError(
                "attachment_inline_invalid_base64",
                "inline_base64 attachment data is not valid base64",
                {"field": "attachments"},
            ) from exc
    return total


def _max_inline_bytes(bridge: dict[str, Any]) -> int:
    caps = bridge.get("client_capabilities")
    if isinstance(caps, dict):
        raw = caps.get("max_inline_attachment_bytes")
        if isinstance(raw, int) and 1024 <= raw <= 1_048_576:
            return min(raw, DEFAULT_MAX_INLINE_ATTACHMENT_BYTES)
    return DEFAULT_MAX_INLINE_ATTACHMENT_BYTES


def validate_openclaw_bridge_in_context(context: dict[str, Any]) -> dict[str, Any]:
    """Validate ``context['openclaw_bridge']`` and enforce attachment size policy.

    Returns the validated bridge dict (same structure as input).
    """
    raw = context.get("openclaw_bridge")
    if raw is None:
        raise OpenClawBridgeValidationError(
            "openclaw_bridge_missing",
            "openclaw_bridge key was expected but is missing",
        )
    if not isinstance(raw, dict):
        raise OpenClawBridgeValidationError(
            "openclaw_bridge_type",
            "openclaw_bridge must be an object",
        )
    bridge = raw
    validator = _validator()
    try:
        validator.validate(bridge)
    except ValidationError as exc:
        raise OpenClawBridgeValidationError(
            "openclaw_bridge_schema",
            "openclaw_bridge failed JSON Schema validation",
            {"json_schema_path": str(_find_envelope_schema_path()), "errors": [exc.message]},
        ) from exc

    max_inline = _max_inline_bytes(bridge)
    used = _total_inline_attachment_bytes(bridge)
    if used > max_inline:
        raise OpenClawBridgeValidationError(
            "attachment_inline_too_large",
            f"inline_base64 attachments exceed limit ({used} > {max_inline} bytes)",
            {"used_bytes": used, "max_bytes": max_inline},
        )
    return bridge


def apply_bridge_continuity_to_context(
    context: dict[str, Any],
    bridge: dict[str, Any],
) -> dict[str, Any]:
    """Copy optional continuity ids from the envelope into the top-level context bag.

    Birtha already reads ``engineering_session_id`` from ``context`` for engineering
    workflows; the bridge duplicates those ids for the shell contract. Shell-side
    caches must only **resend** values previously returned by Birtha.
    """
    out = dict(context)
    mapping = (
        ("engineering_session_id", "engineering_session_id"),
        ("task_id", "task_id"),
        ("run_id", "run_id"),
        ("dossier_id", "dossier_id"),
    )
    for bridge_key, ctx_key in mapping:
        val = bridge.get(bridge_key)
        if isinstance(val, str) and val.strip() and not out.get(ctx_key):
            out[ctx_key] = val.strip()
    return out
