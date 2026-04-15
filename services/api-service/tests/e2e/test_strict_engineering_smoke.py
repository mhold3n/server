"""Opt-in live smoke: API strict_engineering query hits agent-platform engineering_workflow.

For agents: mirrors dev/scripts/smoke_strict_engineering_multimodal.sh.
Requires a running API (and reachable agent-platform + control plane from it).
Set RUN_STRICT_ENGINEERING_SMOKE=1 and API_BASE_URL (default http://127.0.0.1:8080).
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STRICT_ENGINEERING_SMOKE", "") != "1",
    reason="Set RUN_STRICT_ENGINEERING_SMOKE=1 for strict-engineering live smoke.",
)


@pytest.mark.asyncio
async def test_api_query_strict_engineering_returns_orchestrator_payload() -> None:
    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    payload = {
        "prompt": (
            "Strict engineering smoke (pytest): summarize required gates for a "
            "documentation-only change."
        ),
        "engagement_mode": "strict_engineering",
        "model": "gpt-4o-mini",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{base}/api/ai/query", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    inner = data.get("result", data)
    assert isinstance(inner, dict), data
    # Orchestrator returns workflow output; final_response may be empty on blocked paths.
    assert "final_response" in inner or "verification_outcome" in inner or "referential_state" in inner, (
        f"unexpected shape: {list(inner.keys())[:20]}"
    )
    if "referential_state" in inner:
        assert isinstance(inner["referential_state"], dict), (
            f"referential_state must be a JSON object for OpenClaw bridge continuity; got {type(inner['referential_state'])}"
        )
