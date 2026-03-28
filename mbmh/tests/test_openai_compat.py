"""Tests for the OpenAI-compatible API server."""

import pytest

from fastapi.testclient import TestClient
from src.agents.task_router import load_agents
from src.runtime.auth import init_auth
from src.runtime.openai_compat import create_openai_app


def _mock_generate(messages, *, temperature=0.7, max_tokens=256, stream=False):
    """Deterministic stub for generation."""
    return "Hello from the test model."


@pytest.fixture
def client(agents_dir, api_keys_file):
    """Build a FastAPI TestClient with real auth and mocked generation."""
    init_auth(api_keys_file)
    registry = load_agents(agents_dir)

    app = create_openai_app(
        agent_registry=registry,
        generate_fn=_mock_generate,
    )
    return TestClient(app)


VALID_HEADER = {"Authorization": "Bearer test-key-001"}
SCOPED_HEADER = {"Authorization": "Bearer scoped-key-002"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_models_requires_auth(client):
    resp = client.get("/v1/models")
    assert resp.status_code == 401


def test_list_models_with_key(client):
    resp = client.get("/v1/models", headers=VALID_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    names = [m["id"] for m in data["data"]]
    assert "test-agent" in names
    assert "other-agent" in names


def test_chat_completions_no_auth(client):
    resp = client.post("/v1/chat/completions", json={
        "model": "test-agent",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 401


def test_chat_completions_bad_key(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test-agent", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


def test_chat_completions_success(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test-agent", "messages": [{"role": "user", "content": "hi"}]},
        headers=VALID_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "Hello from the test model" in data["choices"][0]["message"]["content"]
    assert data["model"] == "test-agent"


def test_chat_completions_unknown_agent(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "nonexistent", "messages": [{"role": "user", "content": "hi"}]},
        headers=VALID_HEADER,
    )
    assert resp.status_code == 404


def test_unscoped_key_accesses_any_agent(client):
    """A key with empty scopes can access any agent."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "other-agent", "messages": [{"role": "user", "content": "hi"}]},
        headers=VALID_HEADER,
    )
    assert resp.status_code == 200


def test_scoped_key_accesses_allowed_agent(client):
    """A scoped key can access agents in its scopes list."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test-agent", "messages": [{"role": "user", "content": "hi"}]},
        headers=SCOPED_HEADER,
    )
    assert resp.status_code == 200


def test_scoped_key_rejected_for_other_agent(client):
    """A scoped key is denied access to agents outside its scopes list."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "other-agent", "messages": [{"role": "user", "content": "hi"}]},
        headers=SCOPED_HEADER,
    )
    assert resp.status_code == 403


def test_chat_completions_normalizes_openai_content_parts(agents_dir, api_keys_file):
    """OpenClaw-style list content must become strings before generate_fn runs."""
    captured: list = []

    def capture_generate(messages, *, temperature=0.7, max_tokens=256, stream=False):
        captured.clear()
        captured.extend(messages)
        return "ok"

    init_auth(api_keys_file)
    registry = load_agents(agents_dir)
    app = create_openai_app(agent_registry=registry, generate_fn=capture_generate)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-agent",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "plain"}]},
            ],
        },
        headers=VALID_HEADER,
    )
    assert resp.status_code == 200
    user_texts = [m["content"] for m in captured if m.get("role") == "user"]
    assert user_texts
    assert all(isinstance(t, str) for t in user_texts)
    assert "plain" in user_texts[-1]
