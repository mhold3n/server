"""Tests for agent registry loading and lookup."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.base import BaseAgent
from src.agents.task_router import load_agents, get_agent


@pytest.fixture
def agents_dir(tmp_path):
    """Create a temp directory with two agent config files."""
    (tmp_path / "test-agent.yaml").write_text(
        "agent_type: test\ntemperature: 0.3\nmax_tokens: 512\ntools_allowed: []\n"
    )
    (tmp_path / "tooled-agent.yaml").write_text(
        "agent_type: tooled\ntemperature: 0.5\nmax_tokens: 1024\ntools_allowed: [filesystem, http]\n"
    )
    return str(tmp_path)


def test_load_agents_from_dir(agents_dir):
    registry = load_agents(agents_dir)
    assert "test-agent" in registry
    assert "tooled-agent" in registry
    assert len(registry) == 2


def test_agent_config_values(agents_dir):
    load_agents(agents_dir)
    agent = get_agent("test-agent")
    assert agent.config.agent_type == "test"
    assert agent.config.temperature == 0.3
    assert agent.config.max_tokens == 512
    assert agent.config.tools_allowed == []


def test_tooled_agent_tools(agents_dir):
    load_agents(agents_dir)
    agent = get_agent("tooled-agent")
    assert "filesystem" in agent.config.tools_allowed
    assert "http" in agent.config.tools_allowed


def test_unknown_agent_raises(agents_dir):
    load_agents(agents_dir)
    with pytest.raises(ValueError, match="Unknown agent"):
        get_agent("nonexistent-agent")


def test_agent_from_dict():
    agent = BaseAgent.from_dict({
        "agent_type": "custom",
        "temperature": 0.9,
        "max_tokens": 2048,
        "tools_allowed": ["github"],
    })
    assert agent.config.agent_type == "custom"
    assert agent.config.tools_allowed == ["github"]


def test_agent_missing_config_file():
    with pytest.raises(FileNotFoundError):
        BaseAgent.from_config_file("/nonexistent/path.yaml")


def test_load_agents_bad_dir():
    registry = load_agents("/nonexistent/dir")
    assert registry == {}
