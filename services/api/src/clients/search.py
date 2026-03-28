"""Search adapters for Meilisearch (local index) and SearXNG (meta web)."""

from __future__ import annotations

from typing import Any

import httpx


async def meili_search(
    base_url: str,
    api_key: str | None,
    index: str,
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/indexes/{index}/search"
    headers: dict[str, str] = {}
    if api_key:
        # Meili supports X-Meili-API-Key header; Authorization: Bearer also works
        headers["X-Meili-API-Key"] = api_key
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url, json={"q": query, "limit": limit}, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", [])
        # normalize: id, title/name, snippet/path
        results: list[dict[str, Any]] = []
        for h in hits:
            results.append(
                {
                    "id": h.get("id") or h.get("_id") or h.get("path") or h.get("url"),
                    "title": h.get("title") or h.get("name") or h.get("filename") or "",
                    "path": h.get("path") or h.get("url") or "",
                    "score": h.get("_rankingScore") or h.get("_score") or None,
                    "meta": h,
                }
            )
        return results


async def searx_search(
    base_url: str,
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/search"
    params = {"q": query, "format": "json", "pageno": 1}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", [])[:limit]
        results: list[dict[str, Any]] = []
        for it in items:
            results.append(
                {
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "content": it.get("content"),
                    "engines": it.get("engines"),
                    "score": it.get("score"),
                }
            )
        return results
