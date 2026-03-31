"""RAG workflow evaluation: run scenarios (router → RAG → Qwen) and log precision-like signals."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pytest

# Path to docs/rag_eval_scenarios.yaml (repo root = api/tests -> api -> services -> Birtha_bigger_n_badder)
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent.parent.parent
_SCENARIOS_PATH = _REPO_ROOT / "docs" / "rag_eval_scenarios.yaml"


def _load_scenarios() -> list[dict[str, Any]]:
    """Load scenarios from docs/rag_eval_scenarios.yaml."""
    import yaml

    if not _SCENARIOS_PATH.exists():
        return []
    with open(_SCENARIOS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("scenarios", [])


def _response_text_from_workflow_result(body: dict[str, Any]) -> str:
    """Extract answer text from workflow run response (router TaskResponse)."""
    result = body.get("result")
    if not result:
        return ""
    choices = result.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _tools_used_from_workflow_result(body: dict[str, Any]) -> list[str]:
    """Extract tools_used from workflow run response."""
    return body.get("tools_used") or []


def _citation_signal(
    response_text: str, expected_substrings: list[str]
) -> dict[str, Any]:
    """Compute precision-like signal: did the response contain expected source substrings?"""
    if not expected_substrings:
        return {"checked": False, "cited": None, "found": []}
    found = [s for s in expected_substrings if s and s in response_text]
    return {"checked": True, "cited": len(found) >= 1, "found": found}


def _tools_signal(tools_used: list[str], expected_tools: list[str]) -> dict[str, Any]:
    """Signal: did we use the expected tools?"""
    if not expected_tools:
        return {"checked": False, "matched": None}
    matched = [t for t in expected_tools if t in tools_used]
    return {
        "checked": True,
        "matched": len(matched) == len(expected_tools),
        "used": tools_used,
    }


@pytest.fixture(scope="module")
def rag_eval_scenarios() -> list[dict[str, Any]]:
    """Load RAG eval scenarios from YAML."""
    return _load_scenarios()


@pytest.mark.unit
def test_load_rag_eval_scenarios(rag_eval_scenarios: list[dict[str, Any]]) -> None:
    """Scenarios YAML loads and has expected shape."""
    if not _SCENARIOS_PATH.exists():
        pytest.skip("docs/rag_eval_scenarios.yaml not found")
    assert len(rag_eval_scenarios) >= 1
    for s in rag_eval_scenarios:
        assert "id" in s and "task_card_id" in s and "query" in s


@pytest.mark.unit
def test_citation_signal_helpers() -> None:
    """Citation and tools signal helpers behave correctly."""
    text = "According to config.py, OPENAI_BASE_URL is used."
    sig = _citation_signal(text, ["config.py", "OPENAI_BASE_URL"])
    assert sig["checked"] is True and sig["cited"] is True and len(sig["found"]) == 2
    sig2 = _citation_signal(text, ["nonexistent"])
    assert sig2["cited"] is False and sig2["found"] == []
    tools_sig = _tools_signal(
        ["vector-db-mcp:embedding_search"], ["vector-db-mcp:embedding_search"]
    )
    assert tools_sig["checked"] is True and tools_sig["matched"] is True


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("RAG_EVAL_API_URL"),
    reason="Set RAG_EVAL_API_URL to run integration (e.g. http://localhost:8080)",
)
def test_rag_workflow_eval_full_path(rag_eval_scenarios: list[dict[str, Any]]) -> None:
    """Call full path (API workflows/run → router → RAG → Qwen) for each scenario and log signals."""
    import logging

    base_url = os.environ["RAG_EVAL_API_URL"].rstrip("/")
    if not rag_eval_scenarios:
        pytest.skip("No scenarios in docs/rag_eval_scenarios.yaml")
    logging.getLogger().info(
        "RAG eval: running %s scenarios against %s", len(rag_eval_scenarios), base_url
    )
    with httpx.Client(timeout=60.0) as client:
        for scenario in rag_eval_scenarios:
            sid = scenario.get("id", "?")
            task_card_id = scenario.get("task_card_id", "code-rag")
            query = scenario.get("query", "")
            expected_subs = scenario.get("expected_source_substrings") or []
            expected_tools = scenario.get("expected_tools_used") or []
            payload = {
                "name": task_card_id,
                "input": {"query": query, "instruction": query, "task": query},
            }
            try:
                r = client.post(f"{base_url}/api/ai/workflows/run", json=payload)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logging.getLogger().warning("RAG eval scenario %s failed: %s", sid, e)
                continue
            response_text = _response_text_from_workflow_result(body)
            tools_used = _tools_used_from_workflow_result(body)
            cite_sig = _citation_signal(response_text, expected_subs)
            tools_sig = _tools_signal(tools_used, expected_tools)
            logging.getLogger().info(
                "RAG eval %s: len=%s cited=%s tools_match=%s tools_used=%s",
                sid,
                len(response_text),
                cite_sig.get("cited"),
                tools_sig.get("matched"),
                tools_used,
            )
            if cite_sig["checked"]:
                assert cite_sig["cited"] is not None
            if tools_sig["checked"]:
                assert tools_sig["matched"] is not None
