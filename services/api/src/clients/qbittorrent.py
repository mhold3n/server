"""Minimal async client for qBittorrent Web API v2.

Supports login, listing torrents, adding, pause/resume.
"""

from __future__ import annotations

from typing import Any

import httpx


class QBittorrentClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str | None,
        *,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password or ""
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> QBittorrentClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        await self._login()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _login(self) -> None:
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api/v2/auth/login"
        resp = await self._client.post(
            url, data={"username": self.username, "password": self.password}
        )
        resp.raise_for_status()
        # On success, qB returns 'Ok.' and sets SID cookie automatically in the client

    async def list_torrents(self) -> list[dict[str, Any]]:
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api/v2/torrents/info"
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def add(self, urls: list[str]) -> dict[str, Any]:
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api/v2/torrents/add"
        resp = await self._client.post(url, data={"urls": "\n".join(urls)})
        resp.raise_for_status()
        return {"status": "ok", "added": len(urls)}

    async def pause(self, hashes: list[str]) -> dict[str, Any]:
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api/v2/torrents/pause"
        resp = await self._client.post(
            url, data={"hashes": "|".join(hashes) if hashes else "all"}
        )
        resp.raise_for_status()
        return {"status": "paused", "hashes": hashes or ["all"]}

    async def resume(self, hashes: list[str]) -> dict[str, Any]:
        assert self._client is not None, "Client not started"
        url = f"{self.base_url}/api/v2/torrents/resume"
        resp = await self._client.post(
            url, data={"hashes": "|".join(hashes) if hashes else "all"}
        )
        resp.raise_for_status()
        return {"status": "resumed", "hashes": hashes or ["all"]}
