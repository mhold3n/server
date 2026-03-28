"""Shared pytest fixtures for MBMH (mbmh/) tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def agents_dir(tmp_path):
    (tmp_path / "test-agent.yaml").write_text(
        "agent_type: test\ntemperature: 0.3\nmax_tokens: 128\ntools_allowed: []\n"
    )
    (tmp_path / "other-agent.yaml").write_text(
        "agent_type: other\ntemperature: 0.5\nmax_tokens: 256\ntools_allowed: []\n"
    )
    return str(tmp_path)


@pytest.fixture
def api_keys_file(tmp_path):
    keys_file = tmp_path / "api_keys.yaml"
    keys_file.write_text(
        'keys:\n'
        '  - key: "test-key-001"\n'
        '    bundle: "latest"\n'
        '    scopes: []\n'
        '  - key: "scoped-key-002"\n'
        '    bundle: "latest"\n'
        '    scopes: ["test-agent"]\n'
    )
    return str(keys_file)
