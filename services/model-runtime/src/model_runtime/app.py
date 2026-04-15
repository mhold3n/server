"""
FastAPI application: bounded /infer/* and /solve/mechanics.

For agents: MOCK_INFER=1 avoids torch; engineering_core owns deterministic solve.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import anyio
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from model_runtime.config import resolved_model_id
from model_runtime.hf_runtime import infer_with_hf
from model_runtime.validate import (
    validate_orchestration_packet,
    validate_solve_request,
    validate_task_packet_coding,
    validate_task_packet_multimodal,
)

app = FastAPI(title="model-runtime", version="0.1.0")

def _openai_chat_response(*, text: str, model: str, latency_ms: float) -> JSONResponse:
    created = int(time.time())
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": latency_ms,
    }
    return JSONResponse(
        {
            "id": f"chatcmpl-{created}",
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage,
        }
    )


def _usage(latency_ms: float, prompt: int = 0, completion: int = 0) -> dict[str, Any]:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "latency_ms": latency_ms,
    }


def _mock_enabled() -> bool:
    return os.environ.get("MOCK_INFER", "").lower() in ("1", "true", "yes")


def _json_prompt(kind: str, body: dict[str, Any]) -> str:
    return (
        f"Input kind: {kind}\n\n"
        f"{json.dumps(body, indent=2, sort_keys=True)}\n\n"
        "Return a concise answer. If structured output is required, include a valid JSON object."
    )


def _task_packet_prompt(kind: str, body: dict[str, Any]) -> str:
    summary = {
        "task_type": body.get("task_type"),
        "objective": body.get("objective"),
        "context_summary": body.get("context_summary"),
        "validation_requirements": body.get("validation_requirements"),
        "routing_metadata": body.get("routing_metadata"),
    }
    return _json_prompt(kind, {k: v for k, v in summary.items() if v is not None})


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness + config snapshot (does not load HF weights)."""
    from model_runtime.hf_runtime import infer_backend_label, loaded_generator_roles

    mock = _mock_enabled()
    roles_cfg: dict[str, dict[str, str]] = {}
    for role in ("general", "coding", "multimodal"):
        mid = resolved_model_id(role)
        roles_cfg[role] = {
            "model_id": mid,
            "infer_backend": infer_backend_label(role),
        }
    loaded: list[str] = []
    if not mock:
        try:
            loaded = loaded_generator_roles()
        except Exception:
            loaded = []
    return {
        "status": "ok",
        "service": "model-runtime",
        "mock_infer": str(mock).lower(),
        "roles": roles_cfg,
        "generators_loaded": loaded,
    }


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
    if _mock_enabled():
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

    try:
        result = await anyio.to_thread.run_sync(
            infer_with_hf,
            "general",
            "You are the model-runtime general inference role. Extract task-relevant facts and preserve uncertainty.",
            _json_prompt("orchestration_packet", body),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(e)) from e
    return JSONResponse(
        {
            "usage": _usage(result.latency_ms, result.prompt_tokens, result.completion_tokens),
            "model_id_resolved": mid,
            "text": result.text,
            "structured_output": result.structured_output or {},
        },
    )


@app.get("/v1/models")
async def openai_models() -> JSONResponse:
    """OpenAI-compatible model listing for local Qwen roles.

    This is a minimal compatibility surface used by OpenAI-style clients.
    """
    # Expose the resolved IDs from the role config as "models".
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {"id": resolved_model_id("general"), "object": "model"},
                {"id": resolved_model_id("coding"), "object": "model"},
                {"id": resolved_model_id("multimodal"), "object": "model"},
            ],
        }
    )


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request) -> JSONResponse:
    """OpenAI-compatible chat completions backed by local HF Qwen weights.

    This endpoint is intentionally small: it supports `messages` with string content
    and returns a single assistant message.
    """
    t0 = time.perf_counter()
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="messages must be a non-empty list")

    system_parts: list[str] = []
    user_parts: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            # Best-effort: extract text parts from OpenAI multimodal arrays.
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if not isinstance(content, str):
            continue
        if role == "system":
            system_parts.append(content)
        elif role in ("user", "assistant"):
            user_parts.append(f"{role}: {content}")

    system_prompt = "\n".join(system_parts).strip() or "You are a helpful assistant."
    user_prompt = "\n".join(user_parts).strip()
    if not user_prompt:
        raise HTTPException(status_code=422, detail="no supported message content found")

    lat = (time.perf_counter() - t0) * 1000
    model = str(body.get("model") or resolved_model_id("general"))
    if _mock_enabled():
        return _openai_chat_response(text="[MOCK] " + user_prompt, model=model, latency_ms=lat)

    try:
        result = await anyio.to_thread.run_sync(
            infer_with_hf,
            "general",
            system_prompt,
            user_prompt,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(e)) from e
    return _openai_chat_response(text=result.text, model=model, latency_ms=result.latency_ms)


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
    if _mock_enabled():
        return JSONResponse(
            {
                "usage": _usage(lat, 5, 20),
                "model_id_resolved": mid,
                "text": "# mock codegen\npass\n",
            },
        )
    try:
        result = await anyio.to_thread.run_sync(
            infer_with_hf,
            "coding",
            "You are the model-runtime coding role. Return implementation guidance or code scoped only to the task packet.",
            _task_packet_prompt("coding_task_packet", body),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(e)) from e
    return JSONResponse(
        {
            "usage": _usage(result.latency_ms, result.prompt_tokens, result.completion_tokens),
            "model_id_resolved": mid,
            "text": result.text,
            "structured_output": result.structured_output or {},
        },
    )


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
    if _mock_enabled():
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
    try:
        result = await anyio.to_thread.run_sync(
            infer_with_hf,
            "multimodal",
            "You are the model-runtime multimodal extraction role. Return packet-scoped extraction results as JSON when possible.",
            _task_packet_prompt("multimodal_task_packet", body),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(e)) from e
    return JSONResponse(
        {
            "usage": _usage(result.latency_ms, result.prompt_tokens, result.completion_tokens),
            "model_id_resolved": mid,
            "text": result.text,
            "structured_output": result.structured_output or {},
        },
    )


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
