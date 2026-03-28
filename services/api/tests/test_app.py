"""Tests for the FastAPI application."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


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

        # Mock the OpenAI response
        class UsageDict(dict):
            def dict(self):
                return self

        mock_response = AsyncMock()
        mock_response.id = sample_chat_response["id"]
        mock_response.object = sample_chat_response["object"]
        mock_response.created = sample_chat_response["created"]
        mock_response.model = sample_chat_response["model"]
        mock_response.choices = sample_chat_response["choices"]
        mock_response.usage = UsageDict(**sample_chat_response["usage"])

        # Ensure client exists (TestClient startup may set it to None on failure)
        if src.app.openai_client is None:
            src.app.openai_client = AsyncMock()
        src.app.openai_client.chat.completions.create.return_value = mock_response

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

        class UsageDict(dict):
            def dict(self):
                return self

        mock_response = AsyncMock()
        mock_response.id = sample_chat_response["id"]
        mock_response.object = sample_chat_response["object"]
        mock_response.created = sample_chat_response["created"]
        mock_response.model = sample_chat_response["model"]
        mock_response.choices = sample_chat_response["choices"]
        mock_response.usage = UsageDict(**sample_chat_response["usage"])

        # Ensure no leftover side effects from other tests
        src.app.openai_client.chat.completions.create.side_effect = None
        src.app.openai_client.chat.completions.create.return_value = mock_response

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
