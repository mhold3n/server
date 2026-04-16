"""OpenClaw ↔ Birtha bridge helpers (envelope validation, idempotency, attachment policy).

For agents: this package implements Phase 1 shell handshake logic for
``context.openclaw_bridge`` on ``POST /api/ai/query``. It must stay thin; Birtha
orchestration schemas live under ``schemas/control-plane/v1``.
"""

from .bridge_request import (
    extract_post_completion_events,
    validate_and_merge_openclaw_bridge,
)
from .idempotency import (
    idempotency_material,
    idempotency_payload_hash,
    load_idempotency_record,
    redis_idempotency_key,
    resolve_idempotency_lookup,
    save_idempotency_record,
)
from .validate import (
    DEFAULT_MAX_INLINE_ATTACHMENT_BYTES,
    OpenClawBridgeValidationError,
    apply_bridge_continuity_to_context,
    validate_openclaw_bridge_in_context,
)

__all__ = [
    "extract_post_completion_events",
    "validate_and_merge_openclaw_bridge",
    "DEFAULT_MAX_INLINE_ATTACHMENT_BYTES",
    "OpenClawBridgeValidationError",
    "apply_bridge_continuity_to_context",
    "idempotency_material",
    "idempotency_payload_hash",
    "load_idempotency_record",
    "redis_idempotency_key",
    "resolve_idempotency_lookup",
    "save_idempotency_record",
    "validate_openclaw_bridge_in_context",
]
