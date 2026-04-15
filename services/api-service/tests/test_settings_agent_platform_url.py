"""Tests for Settings.agent_platform_url env aliases.

For agents: Pydantic accepts AGENT_PLATFORM_URL first, then ORCHESTRATOR_AGENT_PLATFORM_URL,
so root docker-compose can keep using ORCHESTRATOR_AGENT_PLATFORM_URL without silent
misconfiguration against the default ai-gateway hostname.
"""

from __future__ import annotations

import pytest

from src.config import Settings


def test_agent_platform_url_from_orchestrator_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_PLATFORM_URL", raising=False)
    monkeypatch.setenv("ORCHESTRATOR_AGENT_PLATFORM_URL", "http://wrkhrs-agent-platform:8000")
    cfg = Settings()
    assert cfg.agent_platform_url == "http://wrkhrs-agent-platform:8000"


def test_agent_platform_url_prefers_explicit_agent_platform_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_PLATFORM_URL", "http://explicit:7001")
    monkeypatch.setenv("ORCHESTRATOR_AGENT_PLATFORM_URL", "http://ignored:8000")
    cfg = Settings()
    assert cfg.agent_platform_url == "http://explicit:7001"
