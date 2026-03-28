"""Tests for static UI mounts and basic networking behavior."""

from fastapi.testclient import TestClient

from src.app import app


def test_ui_ai_served():
    client = TestClient(app)
    resp = client.get("/ui/ai/")
    assert resp.status_code == 200
    assert b"AI & Agents" in resp.content


def test_ui_vms_served():
    client = TestClient(app)
    resp = client.get("/ui/vms/")
    assert resp.status_code == 200
    assert (
        b"System Control \xc2\xb7 VMs" in resp.content
        or b"System Control" in resp.content
    )
