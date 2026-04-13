from fastapi.testclient import TestClient

import src.router as router_mod
from src.router import app


def test_root_endpoint():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Agent Router"


def test_health_not_configured():
    client = TestClient(app)
    # Force both clients to None to exercise 'not_configured' branches
    router_mod.redis_client = None
    router_mod.api_client = None
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["api"] == "not_configured"
    assert data["services"]["redis"] == "not_configured"
