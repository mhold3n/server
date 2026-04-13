"""
Bridge to `services/structure` deterministic classifier for control-plane routing.

For agents: mutates `sys.path` temporarily to import structure packages; failures are
surfaced to callers for structured routing fallbacks.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any


def _structure_root() -> Path:
    """Resolve `services/structure` from repo root."""
    here = Path(__file__).resolve()
    for p in here.parents:
        candidate = p / "services" / "structure"
        if (candidate / "router" / "classifier.py").exists():
            return candidate
    raise RuntimeError("services/structure not found from control_plane package")


def classify_user_input(*, user_input: str, request_id: str | None = None) -> dict[str, Any]:
    """
    Run structure `classify_task` and return TaskSpec as JSON-serializable dict.

    Raises ImportError or Exception if structure stack is unavailable.
    """
    structure_root = _structure_root()
    rid = request_id or str(uuid.uuid4())
    inserted = False
    if str(structure_root) not in sys.path:
        sys.path.insert(0, str(structure_root))
        inserted = True
    try:
        from models.task_spec import Partition, TaskRequest
        from router.classifier import classify_task

        req = TaskRequest(
            request_id=rid,
            user_input=user_input,
            partition=Partition.TRAIN,
            context={},
        )
        spec = classify_task(req)
        return spec.model_dump(mode="json")
    finally:
        if inserted:
            try:
                sys.path.remove(str(structure_root))
            except ValueError:
                pass
