"""OpenTelemetry tracing configuration and utilities."""

import os
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger()


class TraceContext:
    """OpenTelemetry trace context manager."""

    def __init__(
        self,
        service_name: str = "birtha-api",
        service_version: str = "0.1.0",
        tempo_endpoint: str = "http://tempo:4317",
    ):
        """Initialize trace context.

        Args:
            service_name: Name of the service
            service_version: Version of the service
            tempo_endpoint: Tempo OTLP endpoint
        """
        self.service_name = service_name
        self.service_version = service_version
        self.tempo_endpoint = tempo_endpoint
        self.tracer = None
        self._setup_tracing()

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        try:
            # Create resource
            resource = Resource.create(
                {
                    "service.name": self.service_name,
                    "service.version": self.service_version,
                    "service.instance.id": os.getenv("HOSTNAME", "unknown"),
                }
            )

            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)

            # Create OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.tempo_endpoint,
                insecure=True,
            )

            # Create span processor
            span_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(span_processor)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)

            logger.info(
                "OpenTelemetry tracing configured",
                service=self.service_name,
                endpoint=self.tempo_endpoint,
            )

        except Exception as e:
            logger.error("Failed to setup OpenTelemetry tracing", error=str(e))
            # Create a no-op tracer
            self.tracer = trace.NoOpTracer()

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application.

        Args:
            app: FastAPI application instance
        """
        try:
            FastAPIInstrumentor.instrument_app(
                app, tracer_provider=trace.get_tracer_provider()
            )
            logger.info("FastAPI instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument FastAPI", error=str(e))

    def instrument_httpx(self) -> None:
        """Instrument HTTPX client."""
        try:
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTPX client instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument HTTPX", error=str(e))

    def instrument_requests(self) -> None:
        """Instrument requests library."""
        try:
            RequestsInstrumentor().instrument()
            logger.info("Requests library instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument requests", error=str(e))

    def get_tracer(self):
        """Get tracer instance.

        Returns:
            Tracer instance
        """
        return self.tracer

    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ):
        """Create a new span.

        Args:
            name: Span name
            attributes: Optional span attributes

        Returns:
            Span context manager
        """
        return self.tracer.start_span(name, attributes=attributes)

    def add_span_attributes(
        self,
        span,
        attributes: dict[str, Any],
    ) -> None:
        """Add attributes to span.

        Args:
            span: Span instance
            attributes: Attributes to add
        """
        if span and span.is_recording():
            for key, value in attributes.items():
                span.set_attribute(key, value)

    def add_span_event(
        self,
        span,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add event to span.

        Args:
            span: Span instance
            name: Event name
            attributes: Optional event attributes
        """
        if span and span.is_recording():
            span.add_event(name, attributes=attributes)

    def set_span_status(
        self,
        span,
        status_code: str,
        description: str | None = None,
    ) -> None:
        """Set span status.

        Args:
            span: Span instance
            status_code: Status code (OK, ERROR, UNSET)
            description: Optional status description
        """
        if span and span.is_recording():
            from opentelemetry.trace import Status, StatusCode

            if status_code == "OK":
                span.set_status(Status(StatusCode.OK, description))
            elif status_code == "ERROR":
                span.set_status(Status(StatusCode.ERROR, description))
            else:
                span.set_status(Status(StatusCode.UNSET, description))


# Global trace context instance
trace_context = TraceContext()


def get_trace_context() -> TraceContext:
    """Get global trace context.

    Returns:
        Trace context instance
    """
    return trace_context


def get_tracer():
    """Get tracer instance.

    Returns:
        Tracer instance
    """
    return trace_context.get_tracer()


def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
):
    """Create a new span.

    Args:
        name: Span name
        attributes: Optional span attributes

    Returns:
        Span context manager
    """
    return trace_context.create_span(name, attributes)


def add_span_attributes(
    span,
    attributes: dict[str, Any],
) -> None:
    """Add attributes to span.

    Args:
        span: Span instance
        attributes: Attributes to add
    """
    trace_context.add_span_attributes(span, attributes)


def add_span_event(
    span,
    name: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Add event to span.

    Args:
        span: Span instance
        name: Event name
        attributes: Optional event attributes
    """
    trace_context.add_span_event(span, name, attributes)


def set_span_status(
    span,
    status_code: str,
    description: str | None = None,
) -> None:
    """Set span status.

    Args:
        span: Span instance
        status_code: Status code (OK, ERROR, UNSET)
        description: Optional status description
    """
    trace_context.set_span_status(span, status_code, description)
