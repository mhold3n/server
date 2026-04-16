"""Redis-backed idempotency for OpenClaw-originated ``/api/ai/query`` turns.

For agents: keys are ``birtha:openclaw-bridge:v1:idempotency:{idempotency_key}``.
Values are JSON ``{"payload_hash": "<sha256>", "response": {...}}`` with TTL.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

IdempotencyOutcome = Literal["miss", "conflict"] | dict[str, Any]

_IDEMPOTENCY_PREFIX = "birtha:openclaw-bridge:v1:idempotency:"
_DEFAULT_TTL_S = 86_400
_MAX_CACHED_RESPONSE_BYTES = 262_144


def redis_idempotency_key(idempotency_key: str) -> str:
    return f"{_IDEMPOTENCY_PREFIX}{idempotency_key}"


def idempotency_material(req: Any) -> dict[str, Any]:
    """Stable dict of request fields that must participate in replay identity."""
    return {
        "prompt": req.prompt,
        "messages": req.messages,
        "model": req.model,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "tools": req.tools,
        "tool_args": req.tool_args,
        "context": req.context,
        "system": req.system,
        "provider": req.provider,
        "engagement_mode": req.engagement_mode,
        "use_router": req.use_router,
    }


def idempotency_payload_hash(req: Any) -> str:
    blob = idempotency_material(req)
    canonical = json.dumps(blob, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def load_idempotency_record(
    redis: Any, idempotency_key: str
) -> dict[str, Any] | None:
    raw = await redis.get(redis_idempotency_key(idempotency_key))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def save_idempotency_record(
    redis: Any,
    *,
    idempotency_key: str,
    payload_hash: str,
    response: dict[str, Any],
    ttl_s: int = _DEFAULT_TTL_S,
) -> None:
    body = json.dumps({"payload_hash": payload_hash, "response": response}, default=str)
    if len(body.encode("utf-8")) > _MAX_CACHED_RESPONSE_BYTES:
        return
    await redis.setex(redis_idempotency_key(idempotency_key), ttl_s, body)


def resolve_idempotency_lookup(
    record: dict[str, Any] | None,
    payload_hash: str,
) -> IdempotencyOutcome:
    """Return cached response dict, ``miss``, or ``conflict``."""
    if record is None:
        return "miss"
    stored_hash = record.get("payload_hash")
    if stored_hash != payload_hash:
        return "conflict"
    resp = record.get("response")
    return resp if isinstance(resp, dict) else "miss"
