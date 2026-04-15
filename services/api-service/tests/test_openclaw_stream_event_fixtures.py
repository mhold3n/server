"""Golden JSON fixtures for ``schemas/openclaw-bridge/v1/events/stream-event.schema.json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "schemas/openclaw-bridge/v1/events/stream-event.schema.json"
_FIXTURE_DIR = _REPO_ROOT / "schemas/openclaw-bridge/v1/events/fixtures"


@pytest.fixture(scope="module")
def stream_event_validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "path",
    sorted(_FIXTURE_DIR.glob("*.json")),
    ids=lambda p: p.name,
)
def test_stream_event_fixture_matches_schema(
    path: Path,
    stream_event_validator: Draft202012Validator,
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    stream_event_validator.validate(data)
