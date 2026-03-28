"""OpenTelemetry end-to-end tracing implementation."""

import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger()


class TracingContext:
    """OpenTelemetry tracing context manager."""

    def __init__(
        self, service_name: str = "birtha-api", service_version: str = "1.0.0"
    ):
        """Initialize tracing context."""
        self.service_name = service_name
        self.service_version = service_version
        self.tracer = None
        self._setup_tracing()

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing."""
        try:
            # Create resource
            resource = Resource.create(
                {
                    ResourceAttributes.SERVICE_NAME: self.service_name,
                    ResourceAttributes.SERVICE_VERSION: self.service_version,
                    ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "production",
                }
            )

            # Create tracer provider
            trace.set_tracer_provider(TracerProvider(resource=resource))
            self.tracer = trace.get_tracer(__name__)

            # Create OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint="http://tempo:4317",
                insecure=True,
            )

            # Create span processor
            span_processor = BatchSpanProcessor(otlp_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)

            # Instrument libraries
            self._instrument_libraries()

            logger.info("OpenTelemetry tracing initialized", service=self.service_name)

        except Exception as e:
            logger.error("Failed to initialize OpenTelemetry tracing", error=str(e))

    def _instrument_libraries(self):
        """Instrument common libraries."""
        try:
            # Instrument HTTP clients
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()

            # Instrument Redis
            RedisInstrumentor().instrument()

            # Instrument SQLAlchemy
            SQLAlchemyInstrumentor().instrument()

            logger.info("Library instrumentation completed")

        except Exception as e:
            logger.error("Failed to instrument libraries", error=str(e))

    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumentation completed")
        except Exception as e:
            logger.error("Failed to instrument FastAPI", error=str(e))

    @asynccontextmanager
    async def trace_request(
        self, operation_name: str, attributes: dict[str, Any] | None = None
    ):
        """Context manager for tracing requests."""
        span = self.tracer.start_span(operation_name)

        try:
            # Set attributes
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            # Set span context
            with trace.use_span(span):
                yield span

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            span.end()

    def create_span(self, name: str, attributes: dict[str, Any] | None = None):
        """Create a new span."""
        span = self.tracer.start_span(name)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        return span

    def add_span_attributes(self, span, attributes: dict[str, Any]):
        """Add attributes to span."""
        for key, value in attributes.items():
            span.set_attribute(key, value)

    def add_span_event(self, span, name: str, attributes: dict[str, Any] | None = None):
        """Add event to span."""
        span.add_event(name, attributes or {})

    def set_span_status(self, span, status: str, description: str = ""):
        """Set span status."""
        if status == "OK":
            span.set_status(Status(StatusCode.OK))
        elif status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, description))
        else:
            span.set_status(Status(StatusCode.UNSET, description))


class TracePropagator:
    """Trace context propagation utilities."""

    @staticmethod
    def extract_trace_context(headers: dict[str, str]) -> dict[str, str]:
        """Extract trace context from headers."""
        trace_context = {}

        # Extract W3C trace context
        if "traceparent" in headers:
            trace_context["traceparent"] = headers["traceparent"]

        if "tracestate" in headers:
            trace_context["tracestate"] = headers["tracestate"]

        # Extract custom headers
        for header in ["x-trace-id", "x-run-id", "x-policy-set"]:
            if header in headers:
                trace_context[header] = headers[header]

        return trace_context

    @staticmethod
    def inject_trace_context(
        headers: dict[str, str], trace_context: dict[str, str]
    ) -> dict[str, str]:
        """Inject trace context into headers."""
        for key, value in trace_context.items():
            headers[key] = value

        return headers

    @staticmethod
    def generate_trace_id() -> str:
        """Generate a new trace ID."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_span_id() -> str:
        """Generate a new span ID."""
        return str(uuid.uuid4())


class GoldenTraceValidator:
    """Validates golden trace end-to-end."""

    def __init__(self, tracing_context: TracingContext):
        """Initialize golden trace validator."""
        self.tracing_context = tracing_context

    async def validate_golden_trace(
        self,
        trace_id: str,
        expected_spans: list,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Validate golden trace with expected spans.

        Args:
            trace_id: Trace ID to validate
            expected_spans: List of expected span names
            timeout: Timeout in seconds

        Returns:
            Validation results
        """
        try:
            # Query Tempo for trace
            trace_data = await self._query_trace(trace_id, timeout)

            if not trace_data:
                return {
                    "valid": False,
                    "error": "Trace not found in Tempo",
                    "trace_id": trace_id,
                }

            # Validate spans
            span_names = [
                span.get("operationName", "") for span in trace_data.get("spans", [])
            ]
            missing_spans = set(expected_spans) - set(span_names)
            extra_spans = set(span_names) - set(expected_spans)

            # Check span hierarchy
            hierarchy_valid = self._validate_span_hierarchy(trace_data.get("spans", []))

            # Check trace duration
            duration = trace_data.get("duration", 0)
            duration_valid = duration > 0 and duration < 30000  # Less than 30 seconds

            return {
                "valid": len(missing_spans) == 0 and hierarchy_valid and duration_valid,
                "trace_id": trace_id,
                "duration": duration,
                "span_count": len(span_names),
                "missing_spans": list(missing_spans),
                "extra_spans": list(extra_spans),
                "hierarchy_valid": hierarchy_valid,
                "duration_valid": duration_valid,
            }

        except Exception as e:
            logger.error("Failed to validate golden trace", error=str(e))
            return {
                "valid": False,
                "error": str(e),
                "trace_id": trace_id,
            }

    async def _query_trace(self, trace_id: str, timeout: int) -> dict[str, Any] | None:
        """Query Tempo for trace data."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"http://tempo:3200/api/traces/{trace_id}",
                    headers={"Accept": "application/json"},
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(
                        "Trace not found in Tempo",
                        trace_id=trace_id,
                        status=response.status_code,
                    )
                    return None

        except Exception as e:
            logger.error("Failed to query trace from Tempo", error=str(e))
            return None

    def _validate_span_hierarchy(self, spans: list) -> bool:
        """Validate span hierarchy (parent-child relationships)."""
        try:
            # Build span map
            span_map = {span.get("spanID"): span for span in spans}

            # Check for root span
            root_spans = [span for span in spans if not span.get("parentSpanID")]
            if len(root_spans) != 1:
                return False

            # Check for proper parent-child relationships
            for span in spans:
                parent_id = span.get("parentSpanID")
                if parent_id and parent_id not in span_map:
                    return False

            return True

        except Exception as e:
            logger.error("Failed to validate span hierarchy", error=str(e))
            return False


# Global tracing context
tracing_context = TracingContext()


def get_tracing_context() -> TracingContext:
    """Get global tracing context."""
    return tracing_context


def get_trace_propagator() -> TracePropagator:
    """Get trace propagator instance."""
    return TracePropagator()


def get_golden_trace_validator() -> GoldenTraceValidator:
    """Get golden trace validator instance."""
    return GoldenTraceValidator(tracing_context)
