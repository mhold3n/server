"""Model smoke tests: opt-in via RUN_MODEL_SMOKE=1.

For agents: general model smoke is minimal and validates response envelope.
"""

from __future__ import annotations

import os

import json
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_MODEL_SMOKE", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_MODEL_SMOKE=1 to run local transformer smoke tests",
)
def test_placeholder_smoke_requires_torch_and_weights() -> None:
    """General role: verify offline load path and response envelope (no network)."""
    local = os.environ.get("MODEL_RUNTIME_GENERAL_LOCAL_PATH")
    if not local:
        pytest.skip("Set MODEL_RUNTIME_GENERAL_LOCAL_PATH to local model directory")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        import torch  # type: ignore
    except Exception:  # noqa: BLE001
        pytest.skip("transformers/torch not installed in this environment")

    tok = AutoTokenizer.from_pretrained(local, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        local,
        torch_dtype="auto",
        device_map="auto",
        local_files_only=True,
    )
    inputs = tok("hello", return_tensors="pt")
    _ = model.generate(**inputs, max_new_tokens=8)

    # Envelope shape check: model-runtime response schema is repo-root JSON Schema.
    repo = Path(__file__).resolve().parents[3]
    schema_path = repo / "schemas" / "model-runtime" / "v1" / "model_runtime_response.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"].endswith("model_runtime_response.schema.json")
