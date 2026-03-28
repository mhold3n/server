from __future__ import annotations

import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_worker_settings, settings
from ..workflows import (
    build_tool_args_for_card,
    get_task_card,
    list_task_cards,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])

_worker_settings = get_worker_settings(settings)
DEFAULT_LLM_MODEL = _worker_settings.default_model


class QueryRequest(BaseModel):
    prompt: str | None = Field(default=None)
    messages: list[dict[str, str]] | None = Field(default=None)
    model: str = Field(default=DEFAULT_LLM_MODEL)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    tools: list[str] | None = Field(
        default=None, description="MCP tools to use via router (server:tool)"
    )
    tool_args: dict[str, dict[str, Any]] | None = Field(
        default=None, description="Per-tool argument overrides (key: server:tool)"
    )
    context: dict[str, Any] | None = Field(default=None)
    use_router: bool = Field(
        default=True, description="Route via agent router with MCP integration"
    )
    system: str = Field(default="You are a helpful AI assistant.")


@router.post("/query")
async def ai_query(req: QueryRequest) -> dict[str, Any]:
    if not req.prompt and not req.messages:
        raise HTTPException(status_code=400, detail="Provide 'prompt' or 'messages'")

    if req.use_router:
        payload = {
            "prompt": req.prompt
            or (req.messages[-1]["content"] if req.messages else ""),
            "system": req.system,
            "model": req.model,
            "tools": req.tools,
            "tool_args": req.tool_args,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        # Router calls can take a while when the backing LLM is running locally.
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{settings.router_url}/route", json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(
                    status_code=resp.status_code, detail=resp.text
                ) from None
            return resp.json()
    else:
        # Simple LLM call via AI stack
        payload = {
            "prompt": req.prompt
            or (req.messages[-1]["content"] if req.messages else ""),
            "model": req.model,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.ai_stack_url}/llm/prompt", json=payload
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(
                    status_code=resp.status_code, detail=resp.text
                ) from None
            return resp.json()


class WorkflowRunRequest(BaseModel):
    name: str = Field(
        description="Workflow name (e.g., code-rag, media-fixups, sysadmin-ops)"
    )
    input: dict[str, Any] = Field(default_factory=dict)
    model: str = Field(default=DEFAULT_LLM_MODEL)
    temperature: float = Field(default=0.2)
    max_tokens: int | None = Field(default=None)


@router.get("/tasks")
async def list_tasks() -> dict[str, Any]:
    """Return available task cards for UI/CLI. Used to drive orchestration workflows."""
    cards = list_task_cards()
    return {
        "task_cards": [c.model_dump() for c in cards],
    }


@router.post("/workflows/run")
async def run_workflow(req: WorkflowRunRequest) -> dict[str, Any]:
    name = req.name.lower()
    card = get_task_card(name)
    if not card:
        raise HTTPException(status_code=400, detail=f"Unknown workflow: {req.name}")

    tool_args = build_tool_args_for_card(
        name,
        req.input,
        ai_repos=getattr(settings, "ai_repos", ""),
        marker_processed_dir=getattr(settings, "marker_processed_dir", ""),
    )

    prompt = _workflow_prompt_from_card(name, req.input)
    payload: dict[str, Any] = {
        "prompt": prompt,
        "system": card.system_prompt,
        "model": req.model or DEFAULT_LLM_MODEL,
        "temperature": (
            req.temperature if req.temperature is not None else card.temperature
        ),
        "max_tokens": req.max_tokens if req.max_tokens is not None else card.max_tokens,
    }
    if card.required_tools:
        payload["tools"] = card.required_tools
        payload["tool_args"] = tool_args

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{settings.router_url}/route", json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(
                status_code=resp.status_code, detail=resp.text
            ) from None
        result = resp.json()
        if isinstance(result, dict):
            result["task_card_id"] = name
        return result


def _workflow_prompt_from_card(card_id: str, input_: dict[str, Any]) -> str:
    """Build the user-facing prompt for a task card from input."""
    if card_id == "code-rag":
        return input_.get("query", "Summarize repository context and answer.")
    if card_id == "media-fixups":
        return input_.get("instruction", "Analyze document and propose fixes.")
    if card_id == "sysadmin-ops":
        return input_.get("task", "")
    return input_.get("query", input_.get("prompt", ""))


class SimulationAnalyzeRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    instructions: str = Field(default="Analyze and summarize insights.")
    model: str = Field(default=DEFAULT_LLM_MODEL)


@router.post("/simulations/analyze")
async def simulations_analyze(req: SimulationAnalyzeRequest) -> dict[str, Any]:
    # Simple analysis via AI stack LLM
    prompt = f"Instructions: {req.instructions}\n\nPayload JSON:\n{json.dumps(req.payload, indent=2)}\n\nProvide concise analysis."
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{settings.ai_stack_url}/llm/prompt",
            json={"prompt": prompt, "model": req.model},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(
                status_code=resp.status_code, detail=resp.text
            ) from None
        return resp.json()


def _health_url(path: str, base: str | None) -> str | None:
    if not base:
        return None
    return f"{base.rstrip('/')}{path}"


@router.get("/status")
async def ai_status() -> dict[str, Any]:
    """Aggregate health/status for AI components: API (worker), Qwen, Router, AI Stack, RAG, ASR, MCPs."""
    status: dict[str, Any] = {
        "api": {},
        "router": {},
        "ai_stack": {},
        "worker": {},
        "qwen": {},
        "rag": {},
        "asr": {},
    }

    # API/Worker (OpenAI-compatible client; typically Qwen)
    qwen_reachable = False
    qwen_latency_ms: float | None = None
    qwen_model_name: str | None = None
    try:
        from ..app import openai_client  # lazy import to reuse initialized client

        if openai_client:
            try:
                t0 = time.perf_counter()
                models = await openai_client.models.list()
                qwen_latency_ms = (time.perf_counter() - t0) * 1000
                qwen_reachable = True
                if models.data:
                    first = models.data[0]
                    qwen_model_name = (
                        getattr(first, "id", None) if first is not None else None
                    )
                if not qwen_model_name:
                    qwen_model_name = DEFAULT_LLM_MODEL
                status["worker"] = {
                    "status": "healthy",
                    "model_count": len(models.data),
                }
                status["api"]["openai"] = "healthy"
            except Exception as e:  # pragma: no cover - I/O
                status["worker"] = {"status": "unhealthy", "error": str(e)}
                status["api"]["openai"] = "unhealthy"
        else:
            status["worker"] = {"status": "not_configured"}
            status["api"]["openai"] = "not_configured"
    except Exception:
        status["worker"] = {"status": "unknown"}

    # Qwen section (explicit reachable, model_name, latency)
    status["qwen"] = {
        "reachable": qwen_reachable,
        "model_name": qwen_model_name or DEFAULT_LLM_MODEL,
        "latency_ms": (
            round(qwen_latency_ms, 2) if qwen_latency_ms is not None else None
        ),
    }

    # Router health (+ MCP servers)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{settings.router_url}/health")
            if r.status_code == 200:
                data = r.json()
                status["router"] = {
                    "status": data.get("status", "unknown"),
                    "services": data.get("services", {}),
                    "mcp_servers": data.get("mcp_servers", {}),
                }
            else:
                status["router"] = {"status": "unhealthy", "code": r.status_code}
    except Exception as e:  # pragma: no cover - I/O
        status["router"] = {"status": "unreachable", "error": str(e)}

    # AI Stack health
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{settings.ai_stack_url}/health")
            if r.status_code == 200:
                data = r.json()
                status["ai_stack"] = {"status": "healthy", **data}
            else:
                status["ai_stack"] = {"status": "unhealthy", "code": r.status_code}
    except Exception as e:  # pragma: no cover - I/O
        status["ai_stack"] = {"status": "unreachable", "error": str(e)}

    # RAG worker health (when URL configured)
    rag_url = _health_url("/health", getattr(settings, "rag_health_url", None))
    if rag_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(rag_url)
                if r.status_code == 200:
                    data = r.json()
                    status["rag"] = {
                        "status": data.get("status", "unknown"),
                        "embedding_model_loaded": data.get("embedding_model_loaded"),
                        "qdrant_status": data.get("qdrant_status"),
                    }
                else:
                    status["rag"] = {"status": "unhealthy", "code": r.status_code}
        except Exception as e:  # pragma: no cover - I/O
            status["rag"] = {"status": "unreachable", "error": str(e)}
    else:
        status["rag"] = {"status": "not_configured"}

    # ASR worker health (when URL configured)
    asr_url = _health_url("/health", getattr(settings, "asr_health_url", None))
    if asr_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(asr_url)
                if r.status_code == 200:
                    data = r.json()
                    status["asr"] = {
                        "status": data.get("status", "unknown"),
                        "model_loaded": data.get("model_loaded"),
                        "use_mock": data.get("use_mock"),
                    }
                else:
                    status["asr"] = {"status": "unhealthy", "code": r.status_code}
        except Exception as e:  # pragma: no cover - I/O
            status["asr"] = {"status": "unreachable", "error": str(e)}
    else:
        status["asr"] = {"status": "not_configured"}

    # Profile + worker wiring (for dashboard / debugging)
    try:
        from ..config import WorkerProfile  # type: ignore

        profile_value: str = str(getattr(settings, "orch_profile", WorkerProfile.GPU))
    except Exception:
        profile_value = str(getattr(settings, "orch_profile", "gpu"))

    status["profile"] = profile_value
    status["worker_base_url"] = getattr(settings, "openai_base_url", "")

    # Overall status (worker, router, ai_stack are required; qwen/rag/asr inform but don't fail overall)
    components = [
        status.get("worker", {}),
        status.get("router", {}),
        status.get("ai_stack", {}),
    ]
    overall = (
        "healthy"
        if all(c.get("status") == "healthy" for c in components)
        else "degraded"
    )
    status["status"] = overall
    return status


# =========================
# MCP discovery + control
# =========================


class ToggleRequest(BaseModel):
    enabled: bool = Field(...)


class MCPCallRequest(BaseModel):
    server: str
    tool: str
    arguments: dict[str, Any] | None = None


async def _get_disabled_servers() -> list[str]:
    try:
        from ..app import redis_client  # type: ignore

        if redis_client:
            disabled = await redis_client.smembers("mcp:disabled")
            return list(disabled or [])
    except Exception:
        pass
    return []


async def _set_server_enabled(name: str, enabled: bool) -> None:
    try:
        from ..app import redis_client  # type: ignore

        if not redis_client:
            return
        if enabled:
            await redis_client.srem("mcp:disabled", name)
        else:
            await redis_client.sadd("mcp:disabled", name)
    except Exception:
        pass


@router.get("/mcp/servers")
async def mcp_servers() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{settings.router_url}/mcp/servers")
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text) from None
        data = r.json() or {}
        servers = data.get("servers", [])
        disabled = set(await _get_disabled_servers())
        for s in servers:
            s["enabled"] = s.get("name") not in disabled
        return {"servers": servers}


@router.post("/mcp/servers/{name}/enable")
async def mcp_toggle_server(name: str, body: ToggleRequest) -> dict[str, Any]:
    await _set_server_enabled(name, body.enabled)
    return {"server": name, "enabled": body.enabled}


@router.get("/mcp/servers/{name}/tools")
async def mcp_server_tools(name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{settings.router_url}/mcp/servers/{name}/tools")
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text) from None
        return r.json()


@router.post("/mcp/call")
async def mcp_call(req: MCPCallRequest) -> dict[str, Any]:
    disabled = await _get_disabled_servers()
    if req.server in disabled:
        raise HTTPException(
            status_code=403, detail=f"Server '{req.server}' is disabled"
        )
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Router expects tool_name and arguments; send as JSON body
        r = await client.post(
            f"{settings.router_url}/mcp/servers/{req.server}/call",
            json={"tool_name": req.tool, "arguments": req.arguments or {}},
        )
        try:
            r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=r.status_code, detail=r.text) from None
        return r.json()
