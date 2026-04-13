from unittest.mock import patch

import httpx
import respx
from fastapi.testclient import TestClient

from src.app import app


def test_apps_list_combines_http_and_container_status():
    client = TestClient(app)

    # Mock HTTP endpoints of apps
    with respx.mock() as mock:
        mock.get("http://api:8080/health").mock(return_value=httpx.Response(200))
        mock.get("http://router:8000/health").mock(return_value=httpx.Response(200))
        mock.get("http://grafana:3000/login").mock(return_value=httpx.Response(302))
        mock.get("http://prometheus:9090/-/healthy").mock(
            return_value=httpx.Response(200)
        )
        mock.get("http://homarr:7575").mock(return_value=httpx.Response(200))
        mock.get("http://pihole:80/admin").mock(return_value=httpx.Response(200))

        # Patch container listing in route module
        with patch("src.routes.apps.list_service_containers") as fake_list:
            fake_list.side_effect = lambda s: (
                [{"name": f"{s}.1", "status": "running"}]
                if s in ("api", "router")
                else []
            )
            resp = client.get("/api/apps")
            assert resp.status_code == 200
            items = resp.json()["items"]
            api_item = next(i for i in items if i["id"] == "api")
            assert api_item["http"] == "up" and api_item["container"] == "running"
