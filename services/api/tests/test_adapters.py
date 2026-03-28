import httpx
import respx
from fastapi.testclient import TestClient

import src.config as cfg
from src.app import app


def test_proxmox_vms_list_and_actions(monkeypatch):
    # Ensure credentials set
    monkeypatch.setattr(cfg.settings, "proxmox_token_id", "user@pve!token")
    monkeypatch.setattr(cfg.settings, "proxmox_token_secret", "secret")
    monkeypatch.setattr(cfg.settings, "proxmox_base_url", "https://pve.local:8006")

    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://pve.local:8006/api2/json/cluster/resources").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "vmid": 107,
                            "name": "docker-host",
                            "node": "pve",
                            "status": "stopped",
                            "type": "qemu",
                            "maxmem": 8589934592,
                            "maxcpu": 4,
                        },
                        {
                            "vmid": 104,
                            "name": "openwrt",
                            "node": "pve",
                            "status": "running",
                            "type": "qemu",
                            "maxmem": 2147483648,
                            "maxcpu": 2,
                        },
                    ]
                },
            )
        )
        resp = client.get("/api/vms/")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2 and items[0]["id"] == 107

        # Start VM 107 (needs node/type discovery from list)
        mock.post(
            "https://pve.local:8006/api2/json/nodes/pve/qemu/107/status/start"
        ).mock(return_value=httpx.Response(200, json={"data": None}))
        resp = client.post("/api/vms/107/start")
        assert resp.status_code == 200 and resp.json()["status"] == "started"

        # Stop VM 104
        mock.post(
            "https://pve.local:8006/api2/json/nodes/pve/qemu/104/status/stop"
        ).mock(return_value=httpx.Response(200, json={"data": None}))
        resp = client.post("/api/vms/104/stop")
        assert resp.status_code == 200 and resp.json()["status"] == "stopped"


def test_proxmox_errors(monkeypatch):
    from src import config as cfg

    monkeypatch.setattr(cfg.settings, "proxmox_token_id", "user@pve!token")
    monkeypatch.setattr(cfg.settings, "proxmox_token_secret", "secret")
    monkeypatch.setattr(cfg.settings, "proxmox_base_url", "https://pve.local:8006")
    client = TestClient(app)
    # Missing VMID
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://pve.local:8006/api2/json/cluster/resources").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        resp = client.post("/api/vms/999/start")
        assert resp.status_code == 404
    # Start returns 500 from Proxmox → 502 at API
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://pve.local:8006/api2/json/cluster/resources").mock(
            return_value=httpx.Response(
                200, json={"data": [{"vmid": 1, "node": "pve", "type": "qemu"}]}
            )
        )
        mock.post(
            "https://pve.local:8006/api2/json/nodes/pve/qemu/1/status/start"
        ).mock(return_value=httpx.Response(500, text="error"))
        resp = client.post("/api/vms/1/start")
        assert resp.status_code == 502


def test_qbittorrent_endpoints(monkeypatch):
    # API uses qb_base_url; default is http://gluetun:8080
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://gluetun:8080/api/v2/auth/login").mock(
            return_value=httpx.Response(200, text="Ok.")
        )
        mock.get("http://gluetun:8080/api/v2/torrents/info").mock(
            return_value=httpx.Response(
                200, json=[{"name": "test.torrent", "hash": "abc"}]
            )
        )

        resp = client.get("/api/torrents/")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["name"] == "test.torrent"

        mock.post("http://gluetun:8080/api/v2/torrents/add").mock(
            return_value=httpx.Response(200)
        )
        resp = client.post(
            "/api/torrents/add", json={"urls": ["magnet:?xt=urn:btih:abc"]}
        )
        assert resp.status_code == 200 and resp.json()["added"] == 1

        mock.post("http://gluetun:8080/api/v2/torrents/pause").mock(
            return_value=httpx.Response(200)
        )
        resp = client.post("/api/torrents/pause", json={"hashes": ["abc"]})
        assert resp.status_code == 200 and resp.json()["status"] == "paused"

        mock.post("http://gluetun:8080/api/v2/torrents/resume").mock(
            return_value=httpx.Response(200)
        )
        resp = client.post("/api/torrents/resume", json={"hashes": ["abc"]})
        assert resp.status_code == 200 and resp.json()["status"] == "resumed"


def test_qbittorrent_login_failure():
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://gluetun:8080/api/v2/auth/login").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        resp = client.get("/api/torrents/")
        assert resp.status_code == 502


def test_search_endpoints(monkeypatch):
    client = TestClient(app)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://meilisearch:7700/indexes/files/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "hits": [
                        {
                            "id": "/tmp/file.txt",
                            "title": "file",
                            "path": "/tmp/file.txt",
                        }
                    ]
                },
            )
        )
        mock.get("http://searxng:8080/search").mock(
            return_value=httpx.Response(
                200, json={"results": [{"title": "web", "url": "http://example.com"}]}
            )
        )

        resp = client.get("/api/search", params={"q": "test", "kind": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1 and len(data["web"]) == 1


def test_search_degraded_paths():
    client = TestClient(app)
    with respx.mock() as mock:
        # Meili fails, Searx ok
        mock.post("http://meilisearch:7700/indexes/files/search").mock(
            return_value=httpx.Response(500)
        )
        mock.get("http://searxng:8080/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        resp = client.get("/api/search", params={"q": "test", "kind": "all"})
        assert resp.status_code == 200
        assert resp.json()["files"] == []
    with respx.mock() as mock:
        # Searx fails, Meili ok
        mock.post("http://meilisearch:7700/indexes/files/search").mock(
            return_value=httpx.Response(200, json={"hits": []})
        )
        mock.get("http://searxng:8080/search").mock(return_value=httpx.Response(500))
        resp = client.get("/api/search", params={"q": "test", "kind": "all"})
        assert resp.status_code == 200
        assert resp.json()["web"] == []
