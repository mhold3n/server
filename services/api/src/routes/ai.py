from __future__ import annotations

import json
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_worker_settings, settings
from ..control_plane.engineering import should_auto_promote_engineering
from ..orchestrator_client import OrchestratorClient
from ..workflows import (
    build_tool_args_for_card,
    get_task_card,
    list_task_cards,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])

_worker_settings = get_worker_settings(settings)
DEFAULT_LLM_MODEL = _worker_settings.default_model


async def _call_router_mcp_tool(
    *,
    server: str,
    tool: str,
    arguments: dict[str, Any],
    timeout_s: float = 180.0,
) -> dict[str, Any]:
    """Call an MCP tool via the router's MCP surface.

    This keeps the router as a **tool execution adapter** while orchestration
    decisions and prompt assembly remain in the API + LangGraph pipeline.
    """
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(
            f"{settings.router_url}/mcp/servers/{server}/call",
            json={"tool_name": tool, "arguments": arguments},
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected MCP tool response shape")
        return data


async def _run_required_tools(
    *,
    prompt: str,
    tools: list[str],
    tool_args: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Execute a list of required tools and return their structured results."""
    results: list[dict[str, Any]] = []
    for tool_spec in tools:
        if ":" not in tool_spec:
            raise ValueError(f"Tool spec must be 'server:tool', got: {tool_spec}")
        server, tool = tool_spec.split(":", 1)
        args: dict[str, Any] = {"query": prompt}
        key = f"{server}:{tool}"
        if tool_args and key in tool_args:
            override = tool_args[key]
            if isinstance(override, dict):
                args.update(override)
        out = await _call_router_mcp_tool(server=server, tool=tool, arguments=args)
        results.append(
            {
                "tool": key,
                "arguments": args,
                "result": out.get("result", out),
            }
        )
    return results


class QueryRequest(BaseModel):
    """High-level chat/query request.

    This request is the **canonical** external contract for orchestration-style
    chat. Internally, the control plane forwards it to the LangGraph workflow
    named ``\"wrkhrs_chat\"`` running in the TypeScript agent-platform.

    The `provider` field lets callers express a preference for which backing
    provider to use. The exact routing rules are implemented inside the
    orchestrator; this API simply forwards the hint via `workflow_config`.
    """

    prompt: str | None = Field(default=None)
    messages: list[dict[str, str]] | None = Field(default=None)
    model: str = Field(default=DEFAULT_LLM_MODEL)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    tools: list[str] | None = Field(
        default=None,
        description=(
            "Logical tools to use during orchestration. These are forwarded as part "
            "of the workflow input and may influence which RAG / MCP integrations "
            "the LangGraph workflow activates."
        ),
    )
    tool_args: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Per-tool argument overrides (key: tool identifier). The semantics are "
            "interpreted by the LangGraph workflow and its tools."
        ),
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Opaque context bag forwarded to the workflow as-is.",
    )
    # Kept for backwards compatibility with older callers; the new pipeline
    # always uses the LangGraph orchestrator for routed queries.
    use_router: bool = Field(
        default=True,
        description="Deprecated: retained for compatibility; always routes via orchestrator.",
    )
    system: str = Field(default="You are a helpful AI assistant.")
    provider: str | None = Field(
        default=None,
        description=(
            "Optional provider preference hint for the orchestrator. Expected values "
            "include 'local_worker', 'swarm', or 'hosted_api'. The orchestrator may "
            "ignore unknown values."
        ),
    )


@router.post("/query")
async def ai_query(req: QueryRequest) -> dict[str, Any]:
    """Primary chat/query endpoint backed by the LangGraph orchestrator.

    This endpoint no longer talks directly to the Python router or AI stack
    workers. Instead it delegates to the `wrkhrs_chat` workflow, which owns
    tool selection and provider routing.
    """
    if not req.prompt and not req.messages:
        raise HTTPException(status_code=400, detail="Provide 'prompt' or 'messages'")

    # Normalise into a messages-style payload for the orchestrator.
    if req.messages:
        messages = list(req.messages)
    else:
        messages = [{"role": "user", "content": req.prompt or ""}]

    # Prepend system message if provided.
    if req.system:
        messages = [{"role": "system", "content": req.system}] + messages

    required_tool_results: list[dict[str, Any]] = []
    if req.tools:
        try:
            required_tool_results = await _run_required_tools(
                prompt=req.prompt or (req.messages[-1]["content"] if req.messages else ""),
                tools=req.tools,
                tool_args=req.tool_args,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Required tool execution failed: {exc}",
            ) from exc

    input_data: dict[str, Any] = {
        "messages": messages,
        "model": req.model,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "tools": req.tools,
        "tool_args": req.tool_args,
        "context": req.context,
        "required_tool_results": required_tool_results,
    }
    workflow_config: dict[str, Any] = {}
    workflow_name = "wrkhrs_chat"
    if req.provider:
        workflow_config["provider_preference"] = req.provider
    if req.tools:
        # Tools passed by the caller are treated as required intent for orchestration.
        # The LangGraph workflow decides how to satisfy them.
        workflow_config["strict_tools"] = True
    promotion = should_auto_promote_engineering(
        prompt=req.prompt,
        messages=messages,
        context=req.context,
    )
    if promotion["promote"]:
        workflow_name = "engineering_workflow"
        workflow_config["strict_engineering"] = True
        workflow_config["engineering_promotion_reason"] = promotion["reason"]
        if req.context and req.context.get("engineering_session_id"):
            input_data["engineering_session_id"] = req.context["engineering_session_id"]

    async with OrchestratorClient() as client:
        try:
            result = await client.execute_workflow(
                workflow_name=workflow_name,
                input_data=input_data,
                workflow_config=workflow_config or None,
            )
        except Exception as exc:  # pragma: no cover - network I/O
            raise HTTPException(
                status_code=502,
                detail=f"Orchestrator workflow 'wrkhrs_chat' failed: {exc}",
            ) from exc

    return result


class WorkflowRunRequest(BaseModel):
    name: str = Field(
        description="Workflow name (e.g., code-rag, media-fixups, sysadmin-ops)"
    )
    input: dict[str, Any] = Field(default_factory=dict)
    model: str = Field(default=DEFAULT_LLM_MODEL)
    temperature: float = Field(default=0.2)
    max_tokens: int | None = Field(default=None)
    provider: str | None = Field(
        default=None,
        description=(
            "Optional provider preference hint for this workflow run "
            "('local_worker', 'swarm', or 'hosted_api')."
        ),
    )


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

    # Map task cards onto the canonical LangGraph workflow surface. For now
    # all workflows share the chat-style graph and rely on card metadata to
    # control prompts and tool usage.
    workflow_name = "wrkhrs_chat"
    messages = [
        {"role": "system", "content": card.system_prompt},
        {"role": "user", "content": prompt},
    ]

    required_tool_results: list[dict[str, Any]] = []
    if card.required_tools:
        try:
            required_tool_results = await _run_required_tools(
                prompt=prompt,
                tools=card.required_tools,
                tool_args=tool_args,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Required tool execution failed: {exc}",
            ) from exc

    input_data: dict[str, Any] = {
        "messages": messages,
        "model": req.model or DEFAULT_LLM_MODEL,
        "temperature": (
            req.temperature if req.temperature is not None else card.temperature
        ),
        "max_tokens": req.max_tokens if req.max_tokens is not None else card.max_tokens,
        "tools": card.required_tools or None,
        "tool_args": tool_args or None,
        "required_tool_results": required_tool_results,
        "task_card_id": name,
        "raw_input": req.input,
    }
    workflow_config: dict[str, Any] = {}
    if req.provider:
        workflow_config["provider_preference"] = req.provider
    if card.required_tools:
        workflow_config["strict_tools"] = True

    async with OrchestratorClient() as client:
        try:
            result = await client.execute_workflow(
                workflow_name=workflow_name,
                input_data=input_data,
                workflow_config=workflow_config or None,
            )
        except Exception as exc:  # pragma: no cover - network I/O
            raise HTTPException(
                status_code=502,
                detail=f"Orchestrator workflow '{workflow_name}' failed: {exc}",
            ) from exc

    if isinstance(result, dict) and "result" in result and isinstance(
        result["result"],
        dict,
    ):
        result["result"]["task_card_id"] = name
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
    """Run a lightweight analysis via the LangGraph orchestrator.

    This endpoint intentionally does not talk directly to the legacy AI stack.
    """
    prompt = (
        f"Instructions:\n{req.instructions}\n\n"
        f"Payload JSON:\n{json.dumps(req.payload, indent=2)}\n\n"
        "Provide concise analysis."
    )
    input_data: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "You are a careful analyst."},
            {"role": "user", "content": prompt},
        ],
        "model": req.model,
        "temperature": 0.2,
        "max_tokens": None,
        "tools": None,
        "tool_args": None,
        "context": {"endpoint": "simulations_analyze"},
    }
    async with OrchestratorClient() as client:
        try:
            return await client.execute_workflow(
                workflow_name="wrkhrs_chat",
                input_data=input_data,
                workflow_config=None,
            )
        except Exception as exc:  # pragma: no cover - network I/O
            raise HTTPException(
                status_code=502,
                detail=f"Orchestrator workflow 'wrkhrs_chat' failed: {exc}",
            ) from exc


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
