"""Structured logging and in-process counters for the tool-model lane."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

LANE_LABEL = "tool_model"


@dataclass
class ToolModelMetrics:
    """Lightweight counters for observability (export to Prometheus in production)."""

    requests: int = 0
    rejected_class: int = 0
    rejected_schema: int = 0
    escalations: int = 0
    structured_ok: int = 0
    untrusted_text_ok: int = 0


_METRICS = ToolModelMetrics()


def metrics() -> ToolModelMetrics:
    """Return process-local metrics (useful for tests and single-worker dev)."""
    return _METRICS


def log_lane_event(
    event: str,
    *,
    tool_name: str | None = None,
    correlation_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log line for the tool-model lane."""
    payload: dict[str, Any] = {
        "lane": LANE_LABEL,
        "event": event,
    }
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    if extra:
        payload.update(extra)
    log.info("%s", payload, extra=payload)
