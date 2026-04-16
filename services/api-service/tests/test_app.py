"""Tests for the FastAPI application."""

import types
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_success(self, test_client: TestClient, setup_clients):
        """Test successful health check."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert data["version"] == "0.1.0"
        assert "services" in data

    def test_health_check_with_redis_failure(
        self, test_client: TestClient, mock_openai_client: AsyncMock
    ):
        """Test health check when Redis is unavailable."""
        import src.app

        # Mock Redis failure
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")

        with patch.object(src.app, "redis_client", mock_redis):
            with patch.object(src.app, "openai_client", mock_openai_client):
                response = test_client.get("/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "degraded"
                assert data["services"]["redis"] == "unhealthy"


class TestMetricsEndpoint:
    """Test metrics endpoint."""

    def test_metrics_endpoint(self, test_client: TestClient):
        """Test metrics endpoint returns Prometheus format."""
        response = test_client.get("/metrics")

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/plain; version=0.0.4; charset=utf-8"
        )
        assert "api_requests_total" in response.text

    def test_metrics_disabled(self, test_client: TestClient):
        """Test metrics endpoint when disabled."""
        with patch("src.app.settings.enable_metrics", False):
            response = test_client.get("/metrics")
            assert response.status_code == 404


class TestChatCompletions:
    """Test chat completions endpoint."""

    def test_chat_completions_success(
        self,
        test_client: TestClient,
        setup_clients,
        sample_chat_request: dict,
        sample_chat_response: dict,
    ):
        """Test successful chat completion."""
        import src.app

        completion = ChatCompletion(
            id=sample_chat_response["id"],
            object=sample_chat_response["object"],
            created=sample_chat_response["created"],
            model=sample_chat_response["model"],
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant", content="Test response"
                    ),
                )
            ],
        )

        if src.app.openai_client is None:
            src.app.openai_client = AsyncMock()
        src.app.openai_client.chat.completions.create = AsyncMock(
            return_value=completion
        )

        response = test_client.post("/v1/chat/completions", json=sample_chat_request)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_chat_response["id"]
        assert data["object"] == sample_chat_response["object"]
        assert data["model"] == sample_chat_response["model"]
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["content"] == "Test response"

    def test_chat_completions_no_openai_client(
        self, test_client: TestClient, mock_redis: AsyncMock
    ):
        """Test chat completion when OpenAI client is not available."""
        import src.app

        with patch.object(src.app, "redis_client", mock_redis):
            with patch.object(src.app, "openai_client", None):
                response = test_client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "test",
                        "messages": [{"role": "user", "content": "test"}],
                    },
                )

                assert response.status_code == 503
                assert "OpenAI client not available" in response.json()["detail"]

    def test_chat_completions_openai_error(
        self, test_client: TestClient, setup_clients, sample_chat_request: dict
    ):
        """Test chat completion when OpenAI client raises an error."""
        import src.app

        src.app.openai_client.chat.completions.create.side_effect = Exception(
            "OpenAI error"
        )

        response = test_client.post("/v1/chat/completions", json=sample_chat_request)

        assert response.status_code == 500
        assert "Chat request failed" in response.json()["detail"]

    def test_chat_completions_invalid_request(
        self, test_client: TestClient, setup_clients
    ):
        """Test chat completion with invalid request."""
        invalid_request = {
            "model": "test",
            "messages": [],  # Empty messages should fail validation
        }

        response = test_client.post("/v1/chat/completions", json=invalid_request)

        assert response.status_code == 422  # Validation error

    def test_chat_completions_with_temperature(
        self, test_client: TestClient, setup_clients, sample_chat_response: dict
    ):
        """Test chat completion with custom temperature."""
        import src.app

        completion = ChatCompletion(
            id=sample_chat_response["id"],
            object=sample_chat_response["object"],
            created=sample_chat_response["created"],
            model=sample_chat_response["model"],
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant", content="Test response"
                    ),
                )
            ],
        )

        src.app.openai_client.chat.completions.create = AsyncMock(
            return_value=completion
        )

        request = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.5,
        }

        response = test_client.post("/v1/chat/completions", json=request)

        assert response.status_code == 200

        # Verify temperature was passed to OpenAI client (check last call)
        call_args = src.app.openai_client.chat.completions.create.call_args_list[-1]
        assert call_args.kwargs.get("temperature") == 0.5

    def test_chat_completions_runs_policy_mlflow_and_span_paths(
        self,
        test_client: TestClient,
        setup_clients,
        sample_chat_request: dict,
        sample_chat_response: dict,
    ) -> None:
        """Exercise policy verdict, MLflow logging, and OTel span attribute paths."""
        import src.app
        from src.policies.evidence import PolicyResult
        from src.policies.middleware import PolicyVerdict

        completion = ChatCompletion(
            id=sample_chat_response["id"],
            object=sample_chat_response["object"],
            created=sample_chat_response["created"],
            model=sample_chat_response["model"],
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant", content="Output [1]."
                    ),
                )
            ],
        )

        src.app.openai_client.chat.completions.create = AsyncMock(
            return_value=completion
        )

        verdict = PolicyVerdict(
            overall_passed=True,
            overall_score=0.9,
            total_violations=0,
            total_suggestions=0,
            policy_results={
                "citations": PolicyResult(
                    passed=True,
                    score=0.9,
                    violations=[],
                    suggestions=[],
                    metadata={},
                )
            },
            metadata={},
        )

        fake_span = types.SimpleNamespace(
            is_recording=lambda: True,
            set_attribute=lambda *args, **kwargs: None,
        )

        @contextmanager
        def _fake_start_run(*args, **kwargs):
            yield None

        fake_mlflow = types.SimpleNamespace(
            start_run=_fake_start_run,
            set_tag=lambda *args, **kwargs: None,
            log_metrics=lambda *args, **kwargs: None,
            log_metric=lambda *args, **kwargs: None,
        )

        with patch(
            "src.app.get_request_context",
            return_value={"trace_id": "t", "run_id": "r", "policy_set": "default"},
        ):
            with patch.object(src.app, "mlflow_logger", object()):
                with patch(
                    "src.app.policy_enforcer.validate",
                    new=AsyncMock(return_value=verdict),
                ):
                    with patch(
                        "src.app.trace.get_current_span", return_value=fake_span
                    ):
                        with patch.dict("sys.modules", {"mlflow": fake_mlflow}):
                            resp = test_client.post(
                                "/v1/chat/completions", json=sample_chat_request
                            )

        assert resp.status_code == 200
        assert resp.headers.get("x-policy-verdict") in ("True", "true")
        assert resp.headers.get("x-policy-score") == "0.9"

    def test_chat_completions_blocks_on_policy_when_enabled(
        self,
        test_client: TestClient,
        setup_clients,
        sample_chat_request: dict,
    ) -> None:
        """In block mode, failing policy verdict should return 422."""
        import src.app
        from src.policies.evidence import PolicyResult
        from src.policies.middleware import PolicyVerdict

        completion = ChatCompletion(
            id="chatcmpl-block",
            object="chat.completion",
            created=1,
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant", content="No citations here."
                    ),
                )
            ],
        )
        src.app.openai_client.chat.completions.create = AsyncMock(
            return_value=completion
        )

        verdict = PolicyVerdict(
            overall_passed=False,
            overall_score=0.1,
            total_violations=1,
            total_suggestions=0,
            policy_results={
                "citations": PolicyResult(
                    passed=False,
                    score=0.1,
                    violations=["missing citations"],
                    suggestions=[],
                    metadata={},
                )
            },
            metadata={},
        )

        with patch(
            "src.app.get_request_context", return_value={"policy_set": "default"}
        ):
            with patch(
                "src.app.policy_enforcer.validate", new=AsyncMock(return_value=verdict)
            ):
                with patch.dict("os.environ", {"POLICY_ENFORCEMENT_MODE": "block"}):
                    resp = test_client.post(
                        "/v1/chat/completions", json=sample_chat_request
                    )

        assert resp.status_code == 422
        body = resp.json()
        assert "policy_verdict" in body
        assert resp.headers.get("x-policy-verdict") in ("False", "false")


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint returns API information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Agent Orchestrator API"
        assert data["version"] == "0.1.0"
        assert data["description"] == "Control plane for agent orchestration"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


class TestMiddleware:
    """Test middleware functionality."""

    def test_metrics_middleware(self, test_client: TestClient):
        """Test that metrics middleware collects request metrics."""
        # Make a request
        response = test_client.get("/")
        assert response.status_code == 200

        # Check metrics endpoint for collected data
        metrics_response = test_client.get("/metrics")
        assert metrics_response.status_code == 200
        assert "api_requests_total" in metrics_response.text
        assert "api_request_duration_seconds" in metrics_response.text

    def test_cors_middleware(self, test_client: TestClient):
        """Test CORS middleware allows cross-origin requests."""
        import src.app

        original_debug = src.app.settings.debug
        src.app.settings.debug = True
        try:
            response = test_client.options(
                "/",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            # Ensure CORS preflight returns headers (at least methods)
            assert "access-control-allow-methods" in response.headers
        finally:
            src.app.settings.debug = original_debug


class TestAppHelpers:
    """Coverage for helper functions in src.app."""

    def test_usage_for_log_supports_dict_method(self) -> None:
        import src.app

        class _Obj:
            def dict(self):
                return {"a": 1}

        assert src.app._usage_for_log(_Obj()) == {"a": 1}

    def test_completion_response_body_supports_attr_object(self) -> None:
        import src.app

        obj = types.SimpleNamespace(
            id="x",
            object="chat.completion",
            created=1,
            model="m",
            choices=[],
            usage={"prompt_tokens": 1},
        )
        body = src.app._completion_response_body(obj)
        assert body["id"] == "x"
        assert body["usage"] == {"prompt_tokens": 1}

    def test_usage_for_log_returns_none_for_unexpected_shape(self) -> None:
        import src.app

        class _Obj:
            def dict(self):
                return "not-a-dict"

        assert src.app._usage_for_log(_Obj()) is None

    def test_completion_response_body_prefers_model_dump_and_dict(self) -> None:
        import src.app

        class _ModelDump:
            def model_dump(self):
                return {"ok": True}

        assert src.app._completion_response_body(_ModelDump()) == {"ok": True}

        class _Dict:
            def dict(self):
                return {"ok": "dict"}

        assert src.app._completion_response_body(_Dict()) == {"ok": "dict"}
