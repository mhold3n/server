"""FastAPI router for POST /api/ai/tool-query."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from birtha_tool_model.handler import process_tool_query
from birtha_tool_model.observability import log_lane_event


def get_tool_query_router() -> APIRouter:
    router = APIRouter(tags=["tool-model"])

    @router.post("/api/ai/tool-query")
    async def tool_query(request: Request) -> dict[str, Any]:
        body = await request.json()
        if not isinstance(body, dict):
            log_lane_event("reject_non_object_body")
            return {
                "result_type": "tool_result_rejected",
                "error_code": "schema_validation_failed",
                "message": "Request body must be a JSON object",
            }
        return process_tool_query(body)

    return router
