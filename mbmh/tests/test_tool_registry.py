"""Tests for tool registry and safety validation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.runtime.safety import is_safe_tool_request


def test_allowed_tool():
    config = {"tools_allowed": ["filesystem", "http"]}
    assert is_safe_tool_request(config, "filesystem") is True
    assert is_safe_tool_request(config, "http") is True


def test_rejected_tool():
    config = {"tools_allowed": ["filesystem"]}
    assert is_safe_tool_request(config, "github") is False
    assert is_safe_tool_request(config, "slack") is False


def test_empty_tools_rejects_all():
    config = {"tools_allowed": []}
    assert is_safe_tool_request(config, "filesystem") is False


def test_missing_tools_key():
    config = {}
    assert is_safe_tool_request(config, "anything") is False
