from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from ..clients.docker import DockerUnavailable, list_service_containers, restart_service

router = APIRouter(prefix="/api/apps", tags=["Apps"])


# Minimal catalog for common services exposed in this stack.
# For a real implementation, consider discovering from compose or env.
CATALOG: list[dict[str, str]] = [
    {"id": "api", "name": "API", "url": "http://api:8080/health"},
    {"id": "router", "name": "Router", "url": "http://router:8000/health"},
    {"id": "grafana", "name": "Grafana", "url": "http://grafana:3000/login"},
    {
        "id": "prometheus",
        "name": "Prometheus",
        "url": "http://prometheus:9090/-/healthy",
    },
    {"id": "homarr", "name": "Homarr", "url": "http://homarr:7575"},
    {"id": "pihole", "name": "Pi-hole", "url": "http://pihole:80/admin"},
]


@router.get("")
async def list_apps() -> dict[str, Any]:
    """Return app catalog with HTTP reachability and container status (if available)."""
    items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for app in CATALOG:
            http_status = "unknown"
            try:
                resp = await client.get(app["url"])  # GET for simplicity
                http_status = "up" if 200 <= resp.status_code < 400 else "down"
            except Exception:
                http_status = "down"

            container_status: str = "unavailable"
            try:
                containers = list_service_containers(app["id"])
                # Consider status 'running' if any container is running
                if not containers:
                    container_status = "not_found"
                elif any(c.get("status") == "running" for c in containers):
                    container_status = "running"
                else:
                    # return the first state for visibility
                    container_status = containers[0].get("status", "unknown")
            except DockerUnavailable:
                container_status = "unavailable"
            except Exception:
                container_status = "error"

            items.append({**app, "http": http_status, "container": container_status})
    return {"items": items}


@router.post("/{app_id}/restart")
async def restart_app(app_id: str) -> dict[str, Any]:
    """Restart containers belonging to a compose service via Docker Engine.

    Requires `/var/run/docker.sock` to be mounted and docker SDK installed.
    """
    try:
        result = restart_service(app_id)
        return {"status": "ok", **result}
    except DockerUnavailable as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=500, detail=f"Failed to restart: {e}") from e
