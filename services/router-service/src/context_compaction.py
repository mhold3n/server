"""Compact tool results (e.g. RAG search) into a consistent format for the LLM.

So retrieved evidence is fed to Qwen in a short, consistent block instead of raw JSON.
"""

from __future__ import annotations

import json
from typing import Any


def compact_tool_result_for_llm(
    server_name: str,
    tool_name: str,
    tool_result: Any,
) -> str:
    """Format a tool result for inclusion in the LLM context.

    - If the result looks like a RAG search (has 'evidence' and optionally 'results'),
      return a compact 'Retrieved evidence: ...' block with optional source bullets.
    - Otherwise return a short labeled JSON summary so the LLM still sees the output.
    """
    if isinstance(tool_result, dict):
        evidence = tool_result.get("evidence")
        results = tool_result.get("results")
        if evidence is not None:
            out = f"Retrieved evidence:\n\n{evidence}"
            if results and isinstance(results, list) and len(results) > 0:
                sources = []
                for r in results[:10]:
                    if isinstance(r, dict):
                        src = r.get("source")
                        if not src and isinstance(r.get("metadata"), dict):
                            src = r["metadata"].get("source")
                        if src:
                            sources.append(str(src))
                if sources:
                    out += "\n\nSources: " + "; ".join(sources[:5])
            return out
        # Fallback: one-line summary for other dicts
        return f"Tool result from {server_name}:{tool_name}: {_one_line_summary(tool_result)}"
    return f"Tool result from {server_name}:{tool_name}: {repr(tool_result)[:500]}"


def _one_line_summary(obj: dict[str, Any], max_keys: int = 3) -> str:
    """Produce a short one-line summary of a dict for context."""
    try:
        keys = list(obj.keys())[:max_keys]
        return json.dumps({k: obj[k] for k in keys if k in obj})
    except Exception:
        return "{}"
