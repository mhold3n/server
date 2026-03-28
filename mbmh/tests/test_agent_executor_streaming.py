"""Unit tests for executor streaming behavior (no HTTP)."""

import pytest

from src.agents.base import BaseAgent
from src.agents.executor import agent_loop


@pytest.fixture
def one_shot_agent():
    return BaseAgent.from_dict(
        {
            "agent_type": "test",
            "max_iterations": 3,
            "temperature": 0.1,
            "max_tokens": 64,
        }
    )


def test_stream_callback_receives_string_when_backend_returns_whole_text(one_shot_agent):
    seen: list[str] = []

    def generate_fn(msgs, *, temperature, max_tokens, stream):
        assert stream is True
        return "complete answer"

    def stream_callback(token: str):
        seen.append(token)

    result = agent_loop(
        one_shot_agent,
        [{"role": "user", "content": "q"}],
        generate_fn,
        stream_callback=stream_callback,
    )
    assert result.output == "complete answer"
    assert seen == ["complete answer"]


def test_stream_callback_per_chunk_when_backend_returns_iterator(one_shot_agent):
    seen: list[str] = []

    def generate_fn(msgs, *, temperature, max_tokens, stream):
        assert stream is True
        return iter(["x", "y"])

    def stream_callback(token: str):
        seen.append(token)

    result = agent_loop(
        one_shot_agent,
        [{"role": "user", "content": "q"}],
        generate_fn,
        stream_callback=stream_callback,
    )
    assert result.output == "xy"
    assert seen == ["x", "y"]


def test_no_stream_callback_when_non_streaming_path(one_shot_agent):
    seen: list[str] = []

    def generate_fn(msgs, *, temperature, max_tokens, stream):
        assert stream is False
        return "ok"

    result = agent_loop(
        one_shot_agent,
        [{"role": "user", "content": "q"}],
        generate_fn,
        stream_callback=None,
    )
    assert result.output == "ok"
    assert seen == []
