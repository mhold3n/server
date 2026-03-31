#!/usr/bin/env python3
"""Run RAG workflow evaluation: call API (router → RAG → Qwen) for each scenario and print signals.

Usage:
  python tests/run_rag_eval.py --api-url http://localhost:8080
  RAG_EVAL_API_URL=http://localhost:8080 python tests/run_rag_eval.py

Scenarios are loaded from Birtha_bigger_n_badder/docs/rag_eval_scenarios.yaml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

# Repo root from api/tests
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent.parent.parent
_SCENARIOS_PATH = _REPO_ROOT / "docs" / "rag_eval_scenarios.yaml"


def load_scenarios() -> list[dict]:
    try:
        import yaml
    except ImportError:
        print("pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    if not _SCENARIOS_PATH.exists():
        print(f"Scenarios file not found: {_SCENARIOS_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(_SCENARIOS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("scenarios", [])


def response_text_from_workflow(body: dict) -> str:
    result = body.get("result")
    if not result:
        return ""
    choices = result.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run RAG workflow eval and print signals"
    )
    parser.add_argument(
        "--api-url", default=None, help="API base URL (or set RAG_EVAL_API_URL)"
    )
    args = parser.parse_args()
    api_url = (
        args.api_url or __import__("os").environ.get("RAG_EVAL_API_URL", "")
    ).rstrip("/")
    if not api_url:
        print("Provide --api-url or RAG_EVAL_API_URL", file=sys.stderr)
        return 1

    scenarios = load_scenarios()
    if not scenarios:
        print("No scenarios in docs/rag_eval_scenarios.yaml", file=sys.stderr)
        return 0

    print(f"Running {len(scenarios)} scenarios against {api_url}\n")
    with httpx.Client(timeout=60.0) as client:
        for s in scenarios:
            sid = s.get("id", "?")
            task_card_id = s.get("task_card_id", "code-rag")
            query = s.get("query", "")
            expected_subs = s.get("expected_source_substrings") or []
            expected_tools = s.get("expected_tools_used") or []
            payload = {
                "name": task_card_id,
                "input": {"query": query, "instruction": query, "task": query},
            }
            try:
                r = client.post(f"{api_url}/api/ai/workflows/run", json=payload)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                print(f"  {sid}: ERROR {e}")
                continue
            text = response_text_from_workflow(body)
            tools_used = body.get("tools_used") or []
            cited = (
                any(sub and sub in text for sub in expected_subs)
                if expected_subs
                else None
            )
            tools_ok = (
                (set(expected_tools) <= set(tools_used)) if expected_tools else None
            )
            print(
                f"  {sid}: len={len(text)} cited={cited} tools_ok={tools_ok} tools_used={tools_used}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
