"""
FastAPI application: bounded /infer/* and /solve/mechanics.

For agents: MOCK_INFER=1 avoids torch; engineering_core owns deterministic solve.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from model_runtime.config import resolved_model_id
from model_runtime.validate import (
    validate_orchestration_packet,
    validate_solve_request,
    validate_task_packet_coding,
    validate_task_packet_multimodal,
)

app = FastAPI(title="model-runtime", version="0.1.0")


def _usage(latency_ms: float, prompt: int = 0, completion: int = 0) -> dict[str, Any]:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "latency_ms": latency_ms,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "model-runtime"}


@app.post("/infer/general")
async def infer_general(
    request: Request,
    workflow_root: bool = Query(
        ...,
        description="True only for first packet in branch (parent_packet_id must be null).",
    ),
) -> JSONResponse:
    t0 = time.perf_counter()
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        validate_orchestration_packet(body, workflow_root=workflow_root)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e)) from e

    lat = (time.perf_counter() - t0) * 1000
    mid = resolved_model_id("general")
    if os.environ.get("MOCK_INFER", "").lower() in ("1", "true", "yes"):
        out = {
            "usage": _usage(lat, 10, 32),
            "model_id_resolved": mid,
            "text": (
                '{"summary":"1m steel cube on concrete, horizontal applied force",'
                '"block_material_id":"steel_7850","surface_material_id":"concrete_rough",'
                '"applied_force_N":40000,"cube_side_m":1.0}'
            ),
            "structured_output": {
                "brief_kind": "mechanics_sliding_v1",
                "block_material_id": "steel_7850",
                "surface_material_id": "concrete_rough",
                "applied_force_N": 40000,
                "cube_side_m": 1.0,
            },
        }
        return JSONResponse(out)

    raise HTTPException(
        status_code=503,
        detail="Model load not configured; set MOCK_INFER=1 or implement transformers path",
    )


@app.post("/infer/coding")
async def infer_coding(request: Request) -> JSONResponse:
    t0 = time.perf_counter()
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        validate_task_packet_coding(body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e)) from e
    lat = (time.perf_counter() - t0) * 1000
    mid = resolved_model_id("coding")
    if os.environ.get("MOCK_INFER", "").lower() in ("1", "true", "yes"):
        return JSONResponse(
            {
                "usage": _usage(lat, 5, 20),
                "model_id_resolved": mid,
                "text": "# mock codegen\npass\n",
            },
        )
    raise HTTPException(status_code=503, detail="Set MOCK_INFER=1 or load coding model")


@app.post("/infer/multimodal")
async def infer_multimodal(request: Request) -> JSONResponse:
    t0 = time.perf_counter()
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        validate_task_packet_multimodal(body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e)) from e
    lat = (time.perf_counter() - t0) * 1000
    mid = resolved_model_id("multimodal")
    if os.environ.get("MOCK_INFER", "").lower() in ("1", "true", "yes"):
        return JSONResponse(
            {
                "usage": _usage(lat, 100, 50),
                "model_id_resolved": mid,
                "structured_output": {
                    "extract_kind": "mock_v1",
                    "labels": [],
                },
                "text": "mock multimodal summary",
            },
        )
    raise HTTPException(status_code=503, detail="Set MOCK_INFER=1 or load VL model")


@app.post("/solve/mechanics")
async def solve_mechanics_route(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        validate_solve_request(body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        from engineering_core import solve_mechanics
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Install engineering-core editable: pip install -e ../engineering-core",
        ) from e
    try:
        report = solve_mechanics(body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return JSONResponse(report)


@app.post("/solve/verify")
async def solve_verify(request: Request) -> JSONResponse:
    """Run deterministic verification on an engineering_report_v1 JSON."""
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        from engineering_core import verify_engineering_report
    except ImportError as e:
        raise HTTPException(status_code=500, detail="engineering-core not installed") from e
    return JSONResponse(verify_engineering_report(body))
