"""Request context middleware for provenance tracking."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to propagate trace/run/policy headers through OTel + MLflow."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and add context headers."""
        # Extract or generate context headers
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        run_id = request.headers.get("x-run-id", str(uuid.uuid4()))
        policy_set = request.headers.get("x-policy-set", "default")

        # Attach to request.state for app code
        request.state.trace_id = trace_id
        request.state.run_id = run_id
        request.state.policy_set = policy_set

        # Set OTel span attributes
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("app.trace_id", trace_id)
            span.set_attribute("app.run_id", run_id)
            span.set_attribute("app.policy_set", policy_set)

        logger.info(
            "Request context set",
            trace_id=trace_id,
            run_id=run_id,
            policy_set=policy_set,
            path=request.url.path,
        )

        # Process request
        response = await call_next(request)

        # Add context headers to response for traceability
        response.headers["x-trace-id"] = trace_id
        response.headers["x-run-id"] = run_id
        response.headers["x-policy-set"] = policy_set

        return response


def get_request_context(request: Request) -> dict[str, Any]:
    """Get request context from state.

    Args:
        request: FastAPI request object

    Returns:
        Context dictionary with trace_id, run_id, policy_set
    """
    return {
        "trace_id": getattr(request.state, "trace_id", None),
        "run_id": getattr(request.state, "run_id", None),
        "policy_set": getattr(request.state, "policy_set", "default"),
    }
