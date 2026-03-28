"""
OpenAI Chat Completions contract helpers.

Use these to assert what OpenClaw, the official OpenAI SDK, and other clients rely on:
non-streaming JSON shape, SSE framing, and reconstructable assistant text from deltas.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

Payload = Optional[Dict[str, Any]]


def iter_sse_data_payloads(sse_body: str) -> List[Payload]:
    """
    Parse raw ``text/event-stream`` body into one entry per ``data:`` line.

    ``[DONE]`` markers become ``None``. JSON parse errors propagate.
    """
    out: List[Payload] = []
    for block in sse_body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.split("\n"):
            if not line.startswith("data: "):
                continue
            raw = line[len("data: ") :].strip()
            if raw == "[DONE]":
                out.append(None)
            else:
                out.append(json.loads(raw))
    return out


def reassemble_streaming_assistant_content(payloads: List[Payload]) -> str:
    """Concatenate ``choices[].delta.content`` from streaming chunks (client behavior)."""
    parts: List[str] = []
    for p in payloads:
        if p is None or "error" in p:
            continue
        for choice in p.get("choices") or []:
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if content:
                parts.append(content)
    return "".join(parts)


def assert_openai_non_streaming_completion(
    data: Dict[str, Any],
    *,
    expect_content_substring: Optional[str] = None,
) -> str:
    """Validate a ``chat.completion`` JSON body and return assistant ``content``."""
    assert data.get("object") == "chat.completion", data
    choices = data.get("choices") or []
    assert len(choices) == 1, choices
    msg = choices[0].get("message") or {}
    assert msg.get("role") == "assistant", msg
    content = msg.get("content")
    assert content is not None and str(content).strip() != "", (
        "assistant message content must be non-empty for client UIs"
    )
    if expect_content_substring is not None:
        assert expect_content_substring in str(content)
    return str(content)


def assert_stream_chunks_openai_shaped(payloads: List[Payload]) -> None:
    """Every streaming JSON object (except errors) matches OpenAI chunk layout."""
    for p in payloads:
        if p is None or "error" in p:
            continue
        assert p.get("object") == "chat.completion.chunk", p
        assert "choices" in p and isinstance(p["choices"], list), p
        for c in p["choices"]:
            assert c.get("index") == 0, c
            assert "delta" in c and isinstance(c["delta"], dict), c


def last_stream_finish_reason(payloads: List[Payload]) -> Optional[str]:
    """Return ``finish_reason`` from the last chunk that defines it, if any."""
    last: Optional[str] = None
    for p in payloads:
        if p is None or "error" in p:
            continue
        for c in p.get("choices") or []:
            fr = c.get("finish_reason")
            if fr is not None:
                last = fr
    return last
