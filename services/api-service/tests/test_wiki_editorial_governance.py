"""Tests for wiki proposal schema, queue workflow, and approval transitions."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from response_control_framework.validation import validate_wiki_edit_proposal_json

from src.main import app


def _fixture(relative_path: str) -> dict:
    root = Path(__file__).resolve().parents[3]
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def test_validate_wiki_edit_proposal_fixture() -> None:
    payload = _fixture("xlotyl/services/response-control-framework/schemas/control-plane/v1/fixtures/wiki-edit-proposal/valid-minimal.json")
    proposal = validate_wiki_edit_proposal_json(payload)
    assert proposal.unapproved_source is True
    assert proposal.status.value == "PROPOSED"


def test_wiki_proposal_validation_route_accepts_valid_payload() -> None:
    payload = _fixture("xlotyl/services/response-control-framework/schemas/control-plane/v1/fixtures/wiki-edit-proposal/valid-minimal.json")
    client = TestClient(app)
    response = client.post("/api/control-plane/wiki/proposals/validate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["wiki_edit_proposal"]["caution"] == "unapproved source, proceed with caution"

