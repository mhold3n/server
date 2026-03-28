from unittest import mock

from fastapi.testclient import TestClient

from src.app import app


def test_apps_restart_requires_docker_sdk(monkeypatch):
    client = TestClient(app)
    # Simulate docker SDK missing and no socket
    import src.clients.docker as dock

    monkeypatch.setattr(dock, "docker", None)
    resp = client.post("/api/apps/api/restart")
    assert resp.status_code == 501


def test_apps_restart_success(monkeypatch):
    client = TestClient(app)
    # Fake docker client
    import src.clients.docker as dock

    class FakeContainer:
        def __init__(self, name, status="running"):
            self.name = name
            self.status = status
            self.labels = {}
            self.id = "id-" + name

        def restart(self, timeout=10):
            self.status = "running"

    class FakeClient:
        def __init__(self):
            self.containers = self

        def list(self, all=True, filters=None):  # type: ignore[override]
            return [FakeContainer("api.1", status="exited"), FakeContainer("api.2", status="running")]

        def close(self):
            pass

    # Monkeypatch docker SDK and socket presence
    monkeypatch.setattr(dock, "docker", mock.MagicMock(from_env=lambda: FakeClient()))
    monkeypatch.setattr(dock.os.path, "exists", lambda p: True)

    resp = client.post("/api/apps/api/restart")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "api" and len(data["restarted"]) == 2

