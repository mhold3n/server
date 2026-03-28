"""Unit tests for observability modules."""

import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.observability.context import RequestContextMiddleware, get_request_context
from src.observability.mlflow_logger import MLflowLogger
from src.observability.trace import get_trace_context


class TestRequestContextMiddleware:
    """Test request context middleware."""

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        middleware = RequestContextMiddleware(Mock())
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_header_extraction(self):
        """Test header extraction and context setting."""
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        # Create test request with headers
        trace_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())
        policy_set = "test-policy"

        request = Request(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/test",
                "headers": [
                    (b"x-trace-id", trace_id.encode()),
                    (b"x-run-id", run_id.encode()),
                    (b"x-policy-set", policy_set.encode()),
                ],
            }
        )

        # Mock call_next
        async def call_next(req):
            # Check that context was set
            assert hasattr(req.state, "trace_id")
            assert hasattr(req.state, "run_id")
            assert hasattr(req.state, "policy_set")
            assert req.state.trace_id == trace_id
            assert req.state.run_id == run_id
            assert req.state.policy_set == policy_set

            from fastapi import Response

            return Response(content="OK")

        middleware = RequestContextMiddleware(app)
        response = await middleware.dispatch(request, call_next)

        # Check response headers
        assert response.headers["x-trace-id"] == trace_id
        assert response.headers["x-run-id"] == run_id
        assert response.headers["x-policy-set"] == policy_set

    @pytest.mark.asyncio
    async def test_header_generation(self):
        """Test header generation when not provided."""
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        request = Request(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/test",
                "headers": [],
            }
        )

        async def call_next(req):
            # Check that context was generated
            assert hasattr(req.state, "trace_id")
            assert hasattr(req.state, "run_id")
            assert hasattr(req.state, "policy_set")
            assert req.state.trace_id is not None
            assert req.state.run_id is not None
            assert req.state.policy_set == "default"

            from fastapi import Response

            return Response(content="OK")

        middleware = RequestContextMiddleware(app)
        response = await middleware.dispatch(request, call_next)

        # Check response headers were generated
        assert "x-trace-id" in response.headers
        assert "x-run-id" in response.headers
        assert "x-policy-set" in response.headers

    def test_get_request_context(self):
        """Test get_request_context function."""
        # Mock request with state
        request = Mock()
        request.state.trace_id = "test-trace-id"
        request.state.run_id = "test-run-id"
        request.state.policy_set = "test-policy"

        context = get_request_context(request)

        assert context["trace_id"] == "test-trace-id"
        assert context["run_id"] == "test-run-id"
        assert context["policy_set"] == "test-policy"

    def test_get_request_context_missing_attributes(self):
        """Test get_request_context with missing attributes."""
        # Mock request without state attributes
        request = Mock()
        request.state = Mock()
        del request.state.trace_id
        del request.state.run_id
        del request.state.policy_set

        context = get_request_context(request)

        assert context["trace_id"] is None
        assert context["run_id"] is None
        assert context["policy_set"] == "default"


class TestTraceContext:
    """Test trace context functionality."""

    def test_trace_context_initialization(self):
        """Test trace context initialization."""
        trace_context = get_trace_context()
        assert trace_context is not None

    @patch("src.observability.trace.trace")
    def test_span_attributes(self, mock_trace):
        """Test span attribute setting."""
        # Mock span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        trace_context = get_trace_context()

        # Test adding attributes
        trace_context.add_span_attributes(mock_span, {"test_key": "test_value"})
        mock_span.set_attribute.assert_called_with("test_key", "test_value")

    @patch("src.observability.trace.trace")
    def test_span_events(self, mock_trace):
        """Test span event addition."""
        # Mock span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        trace_context = get_trace_context()

        # Test adding events
        trace_context.add_span_event(mock_span, "test_event", {"key": "value"})
        mock_span.add_event.assert_called_with(
            "test_event", attributes={"key": "value"}
        )

    @patch("src.observability.trace.trace")
    def test_span_status(self, mock_trace):
        """Test span status setting."""
        # Mock span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        trace_context = get_trace_context()

        # Test setting status
        trace_context.set_span_status(mock_span, "OK", "Success")
        mock_span.set_status.assert_called_once()


class TestMLflowLogger:
    """Test MLflow logger functionality."""

    @patch("src.observability.mlflow_logger.mlflow")
    def test_mlflow_logger_initialization(self, mock_mlflow):
        """Test MLflow logger initialization."""
        logger = MLflowLogger(
            tracking_uri="http://test-mlflow:5000", experiment_name="test-experiment"
        )

        assert logger.tracking_uri == "http://test-mlflow:5000"
        assert logger.experiment_name == "test-experiment"
        mock_mlflow.set_tracking_uri.assert_called_with("http://test-mlflow:5000")

    @patch("src.observability.mlflow_logger.mlflow")
    def test_log_parameters(self, mock_mlflow):
        """Test parameter logging."""
        logger = MLflowLogger()

        from datetime import datetime

        from src.observability.mlflow_logger import EnvironmentSnapshot, RunSpec

        run_spec = RunSpec(prompt="Test prompt", model="test-model", temperature=0.7)

        environment = EnvironmentSnapshot(
            timestamp=datetime.now(),
            service_version="1.0.0",
            model_version="1.0.0",
            config_hash="abc123",
            dependencies={"test": "1.0.0"},
        )

        logger._log_parameters(run_spec, environment)

        mock_mlflow.log_params.assert_called_once()
        params = mock_mlflow.log_params.call_args[0][0]
        assert params["model"] == "test-model"
        assert params["temperature"] == 0.7

    @patch("src.observability.mlflow_logger.mlflow")
    def test_log_metrics(self, mock_mlflow):
        """Test metrics logging."""
        logger = MLflowLogger()

        from src.observability.mlflow_logger import RetrievalDoc, RunSpec, ToolCall

        run_spec = RunSpec(prompt="Test", model="test")
        retrieval_docs = [
            RetrievalDoc(content="test", metadata={}, score=0.8, source="test")
        ]
        tool_calls = [
            ToolCall(
                tool_name="test", tool_args={}, result="ok", duration=1.0, success=True
            )
        ]

        logger._log_metrics(run_spec, retrieval_docs, tool_calls, None)

        mock_mlflow.log_metrics.assert_called_once()
        metrics = mock_mlflow.log_metrics.call_args[0][0]
        assert "prompt_length" in metrics
        assert "retrieval_count" in metrics
        assert "tool_calls_count" in metrics

    @patch("src.observability.mlflow_logger.mlflow")
    def test_log_tags(self, mock_mlflow):
        """Test tags logging."""
        logger = MLflowLogger()

        from datetime import datetime

        from src.observability.mlflow_logger import EnvironmentSnapshot, RunSpec

        run_spec = RunSpec(
            prompt="Test prompt",
            model="test-model",
            domain_weights={"code": 0.8, "docs": 0.2},
            policies=["evidence", "hedging"],
        )

        environment = EnvironmentSnapshot(
            timestamp=datetime.now(),
            service_version="1.0.0",
            model_version="1.0.0",
            config_hash="abc123",
            dependencies={},
        )

        logger._log_tags(run_spec, environment, None)

        mock_mlflow.set_tags.assert_called_once()
        tags = mock_mlflow.set_tags.call_args[0][0]
        assert tags["service"] == "birtha-api"
        assert tags["primary_domain"] == "code"
        assert tags["policies_applied"] == "evidence,hedging"

    @patch("src.observability.mlflow_logger.mlflow")
    def test_log_feedback(self, mock_mlflow):
        """Test feedback logging."""
        logger = MLflowLogger()

        feedback = {"rating": 4, "reasons": ["helpful", "accurate"]}

        result = logger.log_feedback("test-run-id", feedback)

        # Should return False if MLflow not available
        assert result is False

    @patch("src.observability.mlflow_logger.mlflow")
    def test_get_run_info(self, mock_mlflow):
        """Test getting run information."""
        logger = MLflowLogger()

        # Mock run object
        mock_run = Mock()
        mock_run.info.run_id = "test-run-id"
        mock_run.info.status = "FINISHED"
        mock_run.info.start_time = 1234567890
        mock_run.info.end_time = 1234567891
        mock_run.info.experiment_id = "exp-123"
        mock_run.data.params = {"model": "test"}
        mock_run.data.metrics = {"score": 0.8}
        mock_run.data.tags = {"service": "test"}

        mock_mlflow.get_run.return_value = mock_run

        run_info = logger.get_run_info("test-run-id")

        assert run_info is not None
        assert run_info["run_id"] == "test-run-id"
        assert run_info["status"] == "FINISHED"
        assert run_info["params"]["model"] == "test"
        assert run_info["metrics"]["score"] == 0.8

    @patch("src.observability.mlflow_logger.mlflow")
    def test_search_runs(self, mock_mlflow):
        """Test searching runs."""
        logger = MLflowLogger()

        # Mock search results
        mock_runs = Mock()
        mock_runs.to_dict.return_value = [
            {"run_id": "run1", "status": "FINISHED"},
            {"run_id": "run2", "status": "RUNNING"},
        ]

        mock_mlflow.search_runs.return_value = mock_runs

        runs = logger.search_runs(filter_string="status='FINISHED'", max_results=10)

        assert len(runs) == 2
        assert runs[0]["run_id"] == "run1"
        assert runs[1]["run_id"] == "run2"


class TestObservabilityIntegration:
    """Test observability integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_request_flow(self):
        """Test full request flow with observability."""
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            context = get_request_context(request)
            return {"context": context}

        client = TestClient(app)

        # Test with headers
        response = client.get(
            "/test",
            headers={
                "x-trace-id": "test-trace-123",
                "x-run-id": "test-run-456",
                "x-policy-set": "test-policy",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["context"]["trace_id"] == "test-trace-123"
        assert data["context"]["run_id"] == "test-run-456"
        assert data["context"]["policy_set"] == "test-policy"

        # Check response headers
        assert response.headers["x-trace-id"] == "test-trace-123"
        assert response.headers["x-run-id"] == "test-run-456"
        assert response.headers["x-policy-set"] == "test-policy"

    @pytest.mark.asyncio
    async def test_request_without_headers(self):
        """Test request without headers generates context."""
        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            context = get_request_context(request)
            return {"context": context}

        client = TestClient(app)

        response = client.get("/test")

        assert response.status_code == 200
        data = response.json()
        assert data["context"]["trace_id"] is not None
        assert data["context"]["run_id"] is not None
        assert data["context"]["policy_set"] == "default"

        # Check response headers were generated
        assert "x-trace-id" in response.headers
        assert "x-run-id" in response.headers
        assert "x-policy-set" in response.headers

    @patch("src.observability.trace.trace")
    def test_otel_integration(self, mock_trace):
        """Test OpenTelemetry integration."""
        # Mock span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span

        # Test span attribute setting
        trace_context = get_trace_context()
        trace_context.add_span_attributes(
            mock_span,
            {
                "app.trace_id": "test-trace",
                "app.run_id": "test-run",
                "app.policy_set": "test-policy",
            },
        )

        # Verify attributes were set
        assert mock_span.set_attribute.call_count == 3
        mock_span.set_attribute.assert_any_call("app.trace_id", "test-trace")
        mock_span.set_attribute.assert_any_call("app.run_id", "test-run")
        mock_span.set_attribute.assert_any_call("app.policy_set", "test-policy")
