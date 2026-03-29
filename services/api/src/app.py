"""FastAPI control plane for agent orchestration."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from opentelemetry import trace
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from starlette.responses import Response as StarletteResponse

from .config import get_worker_settings, settings
from .observability.context import RequestContextMiddleware, get_request_context
from .observability.mlflow_logger import MLflowLogger
from .observability.provenance import ProvenanceLogger
from .observability.trace import get_trace_context
from .policies.middleware import policy_enforcer

# Routers (scaffolded control plane API)
try:
    from .routes import ai as ai_router
    from .routes import apps as apps_router
    from .routes import search as search_router
    from .routes import torrents as torrents_router
    from .routes import vms as vms_router
except Exception:
    vms_router = None  # type: ignore
    torrents_router = None  # type: ignore
    search_router = None  # type: ignore
    apps_router = None  # type: ignore
    ai_router = None  # type: ignore

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def _usage_for_log(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    md = getattr(usage, "model_dump", None)
    if callable(md):
        out = md()
        if isinstance(out, dict):
            return out
    dfn = getattr(usage, "dict", None)
    if callable(dfn):
        out = dfn()
        if isinstance(out, dict):
            return out
    return None


def _completion_response_body(completion: Any) -> dict[str, Any]:
    """Build JSON body for /v1/chat/completions (real SDK model or test doubles)."""
    if isinstance(completion, ChatCompletion):
        return completion.model_dump()
    md = getattr(completion, "model_dump", None)
    if callable(md):
        out = md()
        if isinstance(out, dict):
            return out
    dfn = getattr(completion, "dict", None)
    if callable(dfn):
        out = dfn()
        if isinstance(out, dict):
            return out
    if all(
        hasattr(completion, a) for a in ("id", "object", "created", "model", "choices")
    ):
        return {
            "id": completion.id,
            "object": completion.object,
            "created": completion.created,
            "model": completion.model,
            "choices": completion.choices,
            "usage": _usage_for_log(getattr(completion, "usage", None)),
        }
    raise TypeError("Unsupported chat completion response type")


# Prometheus metrics
REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total number of chat requests",
    ["model", "status"],
)

CHAT_DURATION = Histogram(
    "chat_request_duration_seconds",
    "Chat request duration in seconds",
    ["model"],
)

# Global clients (decode_responses=True → str values in redis-py)
redis_client: Redis[str] | None = None
openai_client: AsyncOpenAI | None = None
mlflow_logger: MLflowLogger | None = None
provenance_logger: ProvenanceLogger | None = None

app = FastAPI(
    title="Agent Orchestrator API",
    description="Control plane for agent orchestration with OpenAI-compatible endpoints",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request context middleware for provenance tracking
app.add_middleware(RequestContextMiddleware)

# Mount routers if import succeeded
if vms_router is not None:
    app.include_router(vms_router.router)
if torrents_router is not None:
    app.include_router(torrents_router.router)
if search_router is not None:
    app.include_router(search_router.router)
if apps_router is not None:
    app.include_router(apps_router.router)
if ai_router is not None:
    app.include_router(ai_router.router)

# Static UI (small SPA panels)
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(_static_dir), html=True), name="ui")


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request model."""

    model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.3",
        description="Model to use for completion",
    )
    messages: list[ChatMessage] = Field(..., description="List of messages")
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = Field(default=False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Chat completion response model."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int]


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    services: dict[str, str]


@app.middleware("http")
async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[StarletteResponse]],
) -> StarletteResponse:
    """Middleware to collect Prometheus metrics."""
    start_time = asyncio.get_event_loop().time()

    response = await call_next(request)

    duration = asyncio.get_event_loop().time() - start_time

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)

    return response


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize clients on startup."""
    global redis_client, openai_client, mlflow_logger, provenance_logger

    logger.info("Starting Agent Orchestrator API", version="0.1.0")

    # Initialize OpenTelemetry tracing
    try:
        trace_context = get_trace_context()
        trace_context.instrument_fastapi(app)
        trace_context.instrument_httpx()
        trace_context.instrument_requests()
        logger.info("OpenTelemetry tracing initialized")
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry", error=str(e))

    # Initialize MLflow logger
    try:
        mlflow_logger = MLflowLogger(
            tracking_uri=getattr(settings, "mlflow_tracking_uri", "http://mlflow:5000"),
            experiment_name="birtha-ai-runs",
        )
        logger.info("MLflow logger initialized")
    except Exception as e:
        logger.error("Failed to initialize MLflow logger", error=str(e))
        mlflow_logger = None

    # Initialize provenance logger
    try:
        if mlflow_logger:
            provenance_logger = ProvenanceLogger(mlflow_logger)
            logger.info("Provenance logger initialized")
    except Exception as e:
        logger.error("Failed to initialize provenance logger", error=str(e))
        provenance_logger = None

    # Initialize Redis client
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis", url=settings.redis_url)
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        redis_client = None

    # Initialize OpenAI client
    try:
        worker_cfg = get_worker_settings(settings)
        openai_client = AsyncOpenAI(
            base_url=worker_cfg.base_url,
            api_key=settings.openai_api_key,
        )
        logger.info(
            "Initialized OpenAI client",
            base_url=worker_cfg.base_url,
            profile=str(settings.orch_profile),
            default_model=worker_cfg.default_model,
        )
    except Exception as e:
        logger.error("Failed to initialize OpenAI client", error=str(e))
        openai_client = None


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    global redis_client

    if redis_client:
        await redis_client.close()
        logger.info("Closed Redis connection")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    services = {}

    # Check Redis
    if redis_client:
        try:
            await redis_client.ping()
            services["redis"] = "healthy"
        except Exception:
            services["redis"] = "unhealthy"
    else:
        services["redis"] = "not_configured"

    # Check OpenAI client
    if openai_client:
        try:
            # Simple test request
            await openai_client.models.list()
            services["openai"] = "healthy"
        except Exception:
            services["openai"] = "unhealthy"
    else:
        services["openai"] = "not_configured"

    return HealthResponse(
        status=(
            "healthy" if all(s == "healthy" for s in services.values()) else "degraded"
        ),
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
        services=services,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, http_request: Request) -> JSONResponse:
    """OpenAI-compatible chat completions endpoint with policy enforcement."""
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="OpenAI client not available",
        )
    # Basic validation: require at least one message
    if not request.messages:
        raise HTTPException(
            status_code=422, detail="'messages' must contain at least one item"
        )

    if request.stream:
        raise HTTPException(
            status_code=501,
            detail="Streaming chat completions are not supported yet",
        )

    start_time = asyncio.get_event_loop().time()

    # Get request context for provenance tracking
    context = get_request_context(http_request)
    trace_id = context.get("trace_id")
    run_id = context.get("run_id")
    policy_set = context.get("policy_set", "default")

    try:
        logger.info(
            "Processing chat request",
            model=request.model,
            message_count=len(request.messages),
            stream=request.stream,
            trace_id=trace_id,
            run_id=run_id,
            policy_set=policy_set,
        )

        # Convert to OpenAI SDK message params (typed for mypy / OpenAI 1.x)
        openai_messages = cast(
            list[ChatCompletionMessageParam],
            [
                {"role": msg.role, "content": msg.content or ""}
                for msg in request.messages
            ],
        )

        # Make request to worker (non-streaming only)
        completion = await openai_client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=False,
        )

        duration = asyncio.get_event_loop().time() - start_time

        # Extract output for policy enforcement
        output_text = ""
        if completion.choices and len(completion.choices) > 0:
            output_text = completion.choices[0].message.content or ""

        # Run policy enforcement
        policy_verdict = None
        if output_text:
            try:
                policy_verdict = await policy_enforcer.validate(
                    output=output_text,
                    retrieval_docs=None,  # TODO: Add retrieval docs from RAG
                    policy_set=policy_set,
                )

                # Log policy verdicts to MLflow
                if mlflow_logger and trace_id:
                    try:
                        import mlflow

                        with mlflow.start_run(run_name=run_id):
                            mlflow.set_tag("trace_id", trace_id)
                            mlflow.set_tag("policy_set", policy_set)

                            # Log policy metrics
                            mlflow.log_metrics(
                                {
                                    "policy_overall_score": policy_verdict.overall_score,
                                    "policy_violations": policy_verdict.total_violations,
                                    "policy_suggestions": policy_verdict.total_suggestions,
                                    "policy_passed": int(policy_verdict.overall_passed),
                                }
                            )

                            # Log individual policy scores
                            for (
                                policy_name,
                                result,
                            ) in policy_verdict.policy_results.items():
                                mlflow.log_metric(
                                    f"policy_{policy_name}_score", result.score
                                )
                                mlflow.log_metric(
                                    f"policy_{policy_name}_violations",
                                    len(result.violations),
                                )

                    except Exception as e:
                        logger.error(
                            "Failed to log policy verdicts to MLflow", error=str(e)
                        )

                # Set OTel span attributes
                span = trace.get_current_span()
                if span and span.is_recording():
                    span.set_attribute(
                        "app.policy_overall_passed", policy_verdict.overall_passed
                    )
                    span.set_attribute(
                        "app.policy_overall_score", policy_verdict.overall_score
                    )
                    span.set_attribute(
                        "app.policy_violations", policy_verdict.total_violations
                    )

                    for policy_name, result in policy_verdict.policy_results.items():
                        span.set_attribute(
                            f"app.policy_{policy_name}_passed", result.passed
                        )
                        span.set_attribute(
                            f"app.policy_{policy_name}_score", result.score
                        )

            except Exception as e:
                logger.error("Policy enforcement failed", error=str(e))

        # Update metrics
        CHAT_REQUESTS.labels(model=request.model, status="success").inc()
        CHAT_DURATION.labels(model=request.model).observe(duration)

        logger.info(
            "Chat request completed",
            model=request.model,
            duration=duration,
            usage=_usage_for_log(getattr(completion, "usage", None)),
            policy_verdict=(
                policy_verdict.model_dump() if policy_verdict is not None else None
            ),
        )

        body = _completion_response_body(completion)
        http_response = JSONResponse(content=body)
        if policy_verdict is not None:
            http_response.headers["x-policy-verdict"] = str(
                policy_verdict.overall_passed
            )
            http_response.headers["x-policy-score"] = str(policy_verdict.overall_score)

        return http_response

    except Exception as e:
        duration = asyncio.get_event_loop().time() - start_time

        # Update metrics
        CHAT_REQUESTS.labels(model=request.model, status="error").inc()
        CHAT_DURATION.labels(model=request.model).observe(duration)

        logger.error(
            "Chat request failed",
            model=request.model,
            error=str(e),
            duration=duration,
            trace_id=trace_id,
        )

        raise HTTPException(
            status_code=500, detail=f"Chat request failed: {str(e)}"
        ) from e


class FeedbackRequest(BaseModel):
    """Feedback request model."""

    run_id: str = Field(..., description="MLflow run ID")
    rating: int = Field(..., ge=1, le=5, description="User rating (1-5)")
    reasons: list[str] = Field(default_factory=list, description="Feedback reasons")
    notes: str | None = Field(default=None, description="Additional notes")


@app.post("/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest) -> dict[str, Any]:
    """Submit feedback for a run.

    Args:
        feedback: Feedback request with run_id, rating, reasons, notes

    Returns:
        Feedback submission result
    """
    try:
        if not provenance_logger:
            raise HTTPException(
                status_code=503,
                detail="Provenance logger not available",
            )

        # Log feedback to MLflow and feedback.jsonl
        provenance_logger.log_feedback(
            run_id=feedback.run_id,
            rating=feedback.rating,
            reasons=feedback.reasons,
            notes=feedback.notes,
        )

        logger.info(
            "Feedback submitted",
            run_id=feedback.run_id,
            rating=feedback.rating,
            reasons=feedback.reasons,
        )

        return {
            "status": "success",
            "message": "Feedback submitted successfully",
            "run_id": feedback.run_id,
        }

    except Exception as e:
        logger.error("Failed to submit feedback", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to submit feedback: {str(e)}"
        ) from e


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Agent Orchestrator API",
        "version": "0.1.0",
        "description": "Control plane for agent orchestration",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics" if settings.enable_metrics else None,
        "endpoints": {
            "vms": "/api/vms",
            "apps": "/api/apps",
            "torrents": "/api/torrents",
            "search": "/api/search",
            "ai": "/api/ai",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
