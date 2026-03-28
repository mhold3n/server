"""
Integration contract: OpenAI-compatible HTTP API as consumed by OpenClaw-style clients.

Guards against regressions where ``stream: true`` is used but the model returns a
full string (no iterator): the UI must still receive non-empty ``delta.content``
events. See ``agent_loop`` stream_callback handling.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.agents.task_router import load_agents
from src.runtime.auth import init_auth
from src.runtime.openai_compat import create_openai_app

from tests.fixtures.openai_client_contract import (
    assert_openai_non_streaming_completion,
    assert_stream_chunks_openai_shaped,
    iter_sse_data_payloads,
    last_stream_finish_reason,
    reassemble_streaming_assistant_content,
)

VALID_HEADER = {"Authorization": "Bearer test-key-001"}


def _openai_client(generate_fn, agents_dir: str, api_keys_file: str) -> TestClient:
    init_auth(api_keys_file)
    registry = load_agents(agents_dir)
    app = create_openai_app(agent_registry=registry, generate_fn=generate_fn)
    return TestClient(app)


def _mock_generate_string_only(messages, *, temperature=0.7, max_tokens=256, stream=False):
    """Like a local HF model path that completes without a token iterator (returns str)."""
    assert isinstance(stream, bool)
    return "Hello from the test model."


def _mock_generate_token_iterator(messages, *, temperature=0.7, max_tokens=256, stream=False):
    text = "Hi OC"
    if stream:
        return iter([c for c in text])
    return text


def _mock_generate_agent_only_list(messages, *, temperature=0.7, max_tokens=256, stream=False):
    """Mirrors ``server._generate`` when no model is loaded and ``stream`` is True."""
    msg = "[No model loaded — server running in agent-only mode]"
    return [msg] if stream else msg


@pytest.mark.parametrize(
    "generate_fn,expect_substring",
    [
        (_mock_generate_string_only, "Hello from the test model"),
        (_mock_generate_token_iterator, "Hi OC"),
        (_mock_generate_agent_only_list, "No model loaded"),
    ],
    ids=["string-backend", "char-iterator-backend", "agent-only-list-backend"],
)
def test_streaming_chat_completion_reassembles_assistant_text(
    agents_dir, api_keys_file, generate_fn, expect_substring
):
    """
    OpenClaw typically uses streaming; assistant text must appear in SSE deltas
    for all supported generate_fn return shapes.
    """
    client = _openai_client(generate_fn, agents_dir, api_keys_file)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "test-agent",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": True,
        },
        headers=VALID_HEADER,
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        body = response.read().decode("utf-8")

    payloads = iter_sse_data_payloads(body)
    assert_stream_chunks_openai_shaped(payloads)
    assert None in payloads, "expected terminal [DONE] sentinel in stream"
    assembled = reassemble_streaming_assistant_content(payloads)
    assert expect_substring in assembled, (assembled, body[:500])
    assert last_stream_finish_reason(payloads) == "stop"


def test_non_streaming_still_returns_nonempty_message(agents_dir, api_keys_file):
    client = _openai_client(_mock_generate_string_only, agents_dir, api_keys_file)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-agent",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        },
        headers=VALID_HEADER,
    )
    assert resp.status_code == 200
    assert_openai_non_streaming_completion(
        resp.json(),
        expect_content_substring="Hello from the test model",
    )


def test_streaming_error_event_is_valid_json(agents_dir, api_keys_file):
    def _broken_generate(messages, *, temperature=0.7, max_tokens=256, stream=False):
        raise RuntimeError("simulated backend failure")

    client = _openai_client(_broken_generate, agents_dir, api_keys_file)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "test-agent",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": True,
        },
        headers=VALID_HEADER,
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    payloads = iter_sse_data_payloads(body)
    assert any(p is not None and "error" in p for p in payloads)
