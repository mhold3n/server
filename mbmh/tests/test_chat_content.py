"""Tests for OpenAI/OpenClaw message content normalization."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.runtime.chat_content import (
    normalize_openai_content,
    normalize_chat_messages,
)


def test_plain_string():
    assert normalize_openai_content("hello") == "hello"


def test_openai_text_parts_list():
    parts = [{"type": "text", "text": "hello world"}]
    assert normalize_openai_content(parts) == "hello world"


def test_openclaw_control_ui_wrapper_stripped():
    raw = (
        "Sender (untrusted metadata):\n```json\n"
        '{"label": "openclaw-control-ui"}\n```\n\n'
        "[Sat 2026-03-28 14:22 PDT] hello world"
    )
    parts = [{"type": "text", "text": raw}]
    assert normalize_openai_content(parts) == "hello world"


def test_normalize_chat_messages_preserves_roles():
    msgs = [
        {"role": "system", "content": "sys"},
        {
            "role": "user",
            "content": [{"type": "text", "text": "hi"}],
        },
    ]
    out = normalize_chat_messages(msgs)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1]["role"] == "user"
    assert out[1]["content"] == "hi"


def test_none_content():
    assert normalize_openai_content(None) == ""
