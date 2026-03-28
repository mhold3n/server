from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ..clients.search import meili_search, searx_search
from ..config import settings

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("")
async def search_all(
    q: str = Query(..., description="Search query"),
    kind: Literal["all", "files", "web"] = Query("all"),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    try:
        files: list[dict[str, Any]] = []
        web: list[dict[str, Any]] = []

        if kind in ("all", "files"):
            try:
                files = await meili_search(
                    base_url=settings.meili_url,
                    api_key=settings.meili_api_key,
                    index=settings.meili_index,
                    query=q,
                    limit=limit,
                )
            except Exception:
                files = []

        if kind in ("all", "web"):
            try:
                web = await searx_search(settings.searx_url, q, limit=limit)
            except Exception:
                web = []

        return {"query": q, "files": files, "web": web}
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/files")
async def search_files(q: str, limit: int = 10) -> dict[str, Any]:
    try:
        items = await meili_search(
            base_url=settings.meili_url,
            api_key=settings.meili_api_key,
            index=settings.meili_index,
            query=q,
            limit=limit,
        )
        return {"query": q, "items": items}
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"Meilisearch error: {e}") from e


@router.get("/web")
async def search_web(q: str, limit: int = 10) -> dict[str, Any]:
    try:
        items = await searx_search(settings.searx_url, q, limit=limit)
        return {"query": q, "items": items}
    except Exception as e:  # pragma: no cover - I/O wrapper
        raise HTTPException(status_code=502, detail=f"SearXNG error: {e}") from e

