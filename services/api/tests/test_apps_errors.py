from unittest.mock import patch

from fastapi.testclient import TestClient

from src.app import app


def test_apps_list_container_error():
    client = TestClient(app)
    with patch("src.routes.apps.list_service_containers", side_effect=RuntimeError("boom")):
        resp = client.get("/api/apps")
        assert resp.status_code == 200
        # Ensure items present and have container status fields; at least one should be 'error'
        data = resp.json()["items"]
        assert any(i.get("container") == "error" for i in data)


def test_apps_restart_error():
    client = TestClient(app)
    with patch("src.routes.apps.restart_service", side_effect=RuntimeError("fail")):
        resp = client.post("/api/apps/api/restart")
        assert resp.status_code == 500

