"""
OpenAI-compatible REST API served via FastAPI.

Endpoints
---------
GET  /health                  → liveness probe
GET  /v1/models               → list available agent names
POST /v1/chat/completions     → chat completion (routed through agent executor)

All /v1/* routes require a Bearer API key.
"""

import time
import uuid
import json
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .auth import require_api_key, AuthEntry
from .chat_content import normalize_chat_messages
from .telemetry import log_trace

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Pydantic request / response models (OpenAI-shaped)
# -----------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: Optional[Any] = None
    name: Optional[str] = None

    class Config:
        extra = "allow"

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

    class Config:
        extra = "allow"


class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage = Field(default_factory=Usage)


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "local"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# -----------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------

def create_openai_app(
    agent_registry,           # Dict[str, BaseAgent]
    generate_fn,              # callable(messages, *, temperature, max_tokens, stream=False) -> str | Iterable
    session_memory=None,      # Optional SessionMemory
    tools: Dict[str, Any] = None,
    safety_check=None,
) -> FastAPI:
    """Build and return a FastAPI application."""

    app = FastAPI(title="AI-Training Local Runtime", version="0.1.0")

    # Stash references in app state so routes can access them
    app.state.agent_registry = agent_registry
    app.state.generate_fn = generate_fn
    app.state.session_memory = session_memory
    app.state.tools = tools or {}
    app.state.safety_check = safety_check

    # ---- health -------------------------------------------------------
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # ---- GET /v1/models -----------------------------------------------
    @app.get("/v1/models")
    async def list_models(auth: AuthEntry = Depends(require_api_key)):
        names = list(app.state.agent_registry.keys())
        return ModelListResponse(
            data=[ModelInfo(id=n) for n in names]
        )

    # ---- POST /v1/chat/completions ------------------------------------
    @app.post("/v1/chat/completions")
    async def chat_completions(
        body: ChatCompletionRequest,
        auth: AuthEntry = Depends(require_api_key),
    ):
        # Resolve agent from the request's "model" field
        agent_name = body.model
        registry = app.state.agent_registry

        if agent_name not in registry:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' not found. Available: {list(registry.keys())}",
            )

        # Scope check: does this key allow this agent?
        if not auth.is_agent_allowed(agent_name):
            raise HTTPException(
                status_code=403,
                detail=f"API key does not have access to agent '{agent_name}'",
            )

        agent = registry[agent_name]

        # Override temperature / max_tokens if the request supplies them
        temperature = body.temperature if body.temperature is not None else agent.config.temperature
        max_tokens = body.max_tokens if body.max_tokens is not None else agent.config.max_tokens

        # Build a generate_fn wrapper that respects per-request overrides
        _gen = app.state.generate_fn

        def scoped_generate(msgs, *, temperature=temperature, max_tokens=max_tokens, stream=False):
            return _gen(
                msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

        raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]
        user_messages = normalize_chat_messages(raw_messages)

        session_id = str(uuid.uuid4())
        log_trace(session_id, "request_start", {"agent": agent_name, "messages": len(user_messages)})

        # ---- Build OpenAI-shaped response -----------------------------
        from ..agents.executor import agent_loop
        
        if body.stream:
            import queue
            import threading
            import anyio
            
            q = queue.Queue()

            def _stream_callback(token: str):
                q.put({"type": "token", "content": token})

            def _run_agent_sync():
                try:
                    res = agent_loop(
                        agent=agent,
                        messages=user_messages,
                        generate_fn=scoped_generate,
                        tools=app.state.tools,
                        safety_check=app.state.safety_check,
                        session_id=session_id,
                        stream_callback=_stream_callback
                    )
                    q.put({"type": "end", "result": res})
                except Exception as e:
                    logger.exception("Agent loop failed during streaming")
                    q.put({"type": "error", "error": str(e)})

            threading.Thread(target=_run_agent_sync, daemon=True).start()

            async def event_stream():
                chunk_id = f"chatcmpl-{session_id[:12]}"
                created = int(time.time())
                
                while True:
                    # Non-blocking get from queue using threadpool
                    item = await anyio.to_thread.run_sync(q.get)
                    
                    if item["type"] == "token":
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": agent_name,
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": item["content"]},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                    
                    elif item["type"] == "end":
                        result = item["result"]
                        finish_chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": agent_name,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop" if result.status == "completed" else "length"
                            }]
                        }
                        yield f"data: {json.dumps(finish_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                        
                        log_trace(session_id, "request_complete", {"status": result.status, "iterations": result.iterations})
                        
                        if app.state.session_memory:
                            try:
                                app.state.session_memory.save_session(
                                    session_id=result.session_id,
                                    agent_name=agent_name,
                                    bundle_id=auth.bundle,
                                    input_messages=user_messages,
                                    tool_trace=result.trace,
                                    final_output=result.output,
                                )
                            except Exception:
                                logger.exception("Failed to persist session %s", session_id)
                        break
                        
                    elif item["type"] == "error":
                        error_chunk = {
                            "error": {"message": item["error"], "type": "server_error"}
                        }
                        yield f"data: {json.dumps(error_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                        break

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        else:
            # Synchronous path backwards-compatibility
            result = agent_loop(
                agent=agent,
                messages=user_messages,
                generate_fn=scoped_generate,
                tools=app.state.tools,
                safety_check=app.state.safety_check,
                session_id=session_id,
            )
            
            log_trace(session_id, "request_complete", {"status": result.status, "iterations": result.iterations})
            
            if app.state.session_memory:
                try:
                    app.state.session_memory.save_session(
                        session_id=result.session_id,
                        agent_name=agent_name,
                        bundle_id=auth.bundle,
                        input_messages=user_messages,
                        tool_trace=result.trace,
                        final_output=result.output,
                    )
                except Exception:
                    logger.exception("Failed to persist session %s", session_id)

            response = ChatCompletionResponse(
                id=f"chatcmpl-{result.session_id[:12]}",
                created=int(time.time()),
                model=agent_name,
                choices=[
                    Choice(
                        message=ChatMessage(role="assistant", content=result.output),
                        finish_reason="stop" if result.status == "completed" else "length",
                    )
                ],
            )
            return response

    return app


# -----------------------------------------------------------------------
# Entrypoint (called by server.py)
# -----------------------------------------------------------------------

def start_openai_app(host: str, port: int, bundle_id: str, **kwargs):
    """Legacy entrypoint — replaced by server.py create_and_run_server."""
    print(
        f"Server started at http://{host}:{port} "
        f"with bundle {bundle_id} serving OpenAI compat layer."
    )
    print("Use server.py → create_and_run_server() for real startup.")
