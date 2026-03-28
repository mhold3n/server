"""
Normalize OpenAI-style chat message content to plain strings.

Clients such as OpenClaw may send ``content`` as a list of parts
(``[{"type": "text", "text": "..."}]``) instead of a raw string. Passing those
through to the tokenizer fallback used to stringify Python lists, which breaks
prompts and model output.
"""

from __future__ import annotations

import re
from typing import Any, List

_OPENCLAW_SENDER_MARK = "Sender (untrusted metadata)"


def normalize_openai_content(content: Any) -> str:
    """Turn OpenAI ``content`` (str, list, or None) into a single string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return _strip_openclaw_control_ui_wrapper(content)
    if isinstance(content, list):
        return _strip_openclaw_control_ui_wrapper(_content_parts_to_text(content))
    if isinstance(content, dict):
        # Single object (some proxies send one block without a list wrapper)
        return _strip_openclaw_control_ui_wrapper(_content_parts_to_text([content]))
    return _strip_openclaw_control_ui_wrapper(str(content))


def normalize_chat_messages(messages: List[dict]) -> List[dict]:
    """Return a copy of messages with string ``content`` fields."""
    out: List[dict] = []
    for m in messages:
        mm = dict(m)
        mm["content"] = normalize_openai_content(mm.get("content"))
        out.append(mm)
    return out


def _content_parts_to_text(parts: list) -> str:
    texts: List[str] = []
    for block in parts:
        if isinstance(block, str):
            texts.append(block)
            continue
        if not isinstance(block, dict):
            texts.append(str(block))
            continue
        t = block.get("type")
        if t == "text" and block.get("text") is not None:
            texts.append(str(block["text"]))
        elif "text" in block and block["text"] is not None:
            texts.append(str(block["text"]))
        elif isinstance(block.get("content"), str):
            texts.append(block["content"])
    return "\n".join(texts) if texts else ""


def _strip_openclaw_control_ui_wrapper(text: str) -> str:
    """
    OpenClaw Control UI often prefixes user text with sender metadata and a
    timestamp line, e.g. ``[Sat 2026-03-28 14:22 PDT] hello``. Keep the part
    after the last bracketed timestamp on the final line.
    """
    if not text or _OPENCLAW_SENDER_MARK not in text:
        return text
    m = re.search(r"\[[^\]]+\]\s*([^\n]+)\s*$", text.rstrip())
    if m:
        return m.group(1).strip()
    return text
