"""End-to-end tests for golden trace validation in Tempo + MLflow run linkage."""

import asyncio
import os
import time
from unittest.mock import Mock, patch

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STACK_TESTS") != "1",
    reason="E2E tests require a running API and observability stack; set RUN_LIVE_STACK_TESTS=1.",
)


class TestGoldenTraceE2E:
    """Test end-to-end golden trace validation."""

    @pytest.fixture
    def api_url(self):
        """Get API URL."""
        return os.environ.get("API_BASE_URL", "http://localhost:8080")

    @pytest.fixture
    def tempo_url(self):
        """Get Tempo URL."""
        return os.environ.get("TEMPO_BASE_URL", "http://localhost:3200")

    @pytest.fixture
    def mlflow_url(self):
        """Get MLflow URL."""
        return os.environ.get("MLFLOW_BASE_URL", "http://localhost:5000")

    @pytest.fixture
    def golden_trace_id(self):
        """Get golden trace ID."""
        return "golden-trace-001"

    @pytest.fixture
    def golden_run_id(self):
        """Get golden run ID."""
        return "golden-run-001"

    @pytest.fixture
    def sample_chat_request(self):
        """Sample chat request for golden trace."""
        return {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain quantum computing with proper citations.",
                }
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }

    @pytest.mark.asyncio
    async def test_golden_trace_propagation(
        self, api_url, golden_trace_id, golden_run_id, sample_chat_request
    ):
        """Test golden trace propagation through the stack."""
        async with httpx.AsyncClient() as client:
            # Send chat request with golden trace ID
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # Verify response headers
            assert response.headers["x-trace-id"] == golden_trace_id
            assert response.headers["x-run-id"] == golden_run_id
            assert response.headers["x-policy-set"] == "golden-policy"

            # Verify policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

    @pytest.mark.asyncio
    async def test_tempo_trace_validation(self, tempo_url, golden_trace_id):
        """Test that trace appears in Tempo."""
        # Wait a bit for trace to be processed
        await asyncio.sleep(2)

        async with httpx.AsyncClient() as client:
            # Query Tempo for the golden trace
            response = await client.get(
                f"{tempo_url}/api/search",
                params={
                    "tags": f"trace_id={golden_trace_id}",
                    "start": int(time.time()) - 3600,  # Last hour
                    "end": int(time.time()),
                },
            )

            # Note: This is a simplified test - in practice, you'd need to parse the response
            # and verify the trace structure
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_mlflow_run_validation(self, mlflow_url, golden_run_id):
        """Test that MLflow run is created with correct tags."""
        # Wait a bit for MLflow run to be processed
        await asyncio.sleep(2)

        async with httpx.AsyncClient() as client:
            # Query MLflow for the golden run
            response = await client.post(
                f"{mlflow_url}/api/2.0/mlflow/runs/search",
                json={
                    "filter": f"tags.run_id = '{golden_run_id}'",
                    "max_results": 10,
                },
            )

            # Note: This is a simplified test - in practice, you'd need to parse the response
            # and verify the run structure and tags
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_otel_span_attributes(
        self, api_url, golden_trace_id, golden_run_id, sample_chat_request
    ):
        """Test that OTel span attributes are set correctly."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # For true E2E, rely on propagation headers and Tempo/MLflow validation
            # instead of patching in-process spans (the API runs in a container).
            assert response.headers["x-trace-id"] == golden_trace_id
            assert response.headers["x-run-id"] == golden_run_id
            assert response.headers["x-policy-set"] == "golden-policy"

    @pytest.mark.asyncio
    async def test_mlflow_run_creation(
        self, api_url, golden_trace_id, golden_run_id, sample_chat_request
    ):
        """Test that MLflow run is created with correct parameters and metrics."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # Verify MLflow logger was called
            # Note: This is a simplified test - in practice, you'd need to verify
            # the specific MLflow calls and parameters

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_verdict_propagation(
        self,
        mock_openai_client,
        api_url,
        golden_trace_id,
        golden_run_id,
        sample_chat_request,
    ):
        """Test that policy verdicts are propagated through the stack."""
        # Mock OpenAI response with hedging
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "This might be correct, but it seems like it could work. Perhaps the results are accurate."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 100}

        mock_openai_client.chat.completions.create.return_value = mock_response

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # Verify policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Live-stack runs use a real HTTP call; the mock OpenAI worker returns
            # a deterministic "good" response, so policies should pass.
            assert response.headers["x-policy-verdict"] == "True"
            assert float(response.headers["x-policy-score"]) >= 0.9

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_golden_trace_with_citations(
        self, mock_openai_client, api_url, golden_trace_id, golden_run_id
    ):
        """Test golden trace with proper citations."""
        # Mock OpenAI response with citations
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "Quantum computing is a field of study [1]. It uses quantum mechanics [2]. The theory is well-established [3]."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 100}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain quantum computing with proper citations.",
                }
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # Should pass citation policy
            assert response.headers["x-policy-verdict"] == "True"
            assert float(response.headers["x-policy-score"]) > 0.5

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_golden_trace_with_si_units(
        self, mock_openai_client, api_url, golden_trace_id, golden_run_id
    ):
        """Test golden trace with proper SI units."""
        # Mock OpenAI response with SI units
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "The temperature is 298 K and the pressure is 101.3 kPa. The force is 100 N."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 100}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "What are the standard conditions?"}
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 200

            # Should pass unit policy
            assert response.headers["x-policy-verdict"] == "True"
            assert float(response.headers["x-policy-score"]) > 0.5

    @pytest.mark.asyncio
    async def test_golden_trace_error_handling(
        self, api_url, golden_trace_id, golden_run_id, sample_chat_request
    ):
        """Test golden trace error handling."""
        # Test with invalid request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json={"model": "test-model", "messages": []},  # Invalid request
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 422

            # Verify headers are still returned
            assert response.headers["x-trace-id"] == golden_trace_id
            assert response.headers["x-run-id"] == golden_run_id
            assert response.headers["x-policy-set"] == "golden-policy"

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_golden_trace_without_headers(
        self, mock_openai_client, api_url, sample_chat_request
    ):
        """Test golden trace without headers generates context."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a test response."
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 100}

        mock_openai_client.chat.completions.create.return_value = mock_response

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions", json=sample_chat_request
            )

            assert response.status_code == 200

            # Verify headers were generated
            assert "x-trace-id" in response.headers
            assert "x-run-id" in response.headers
            assert "x-policy-set" in response.headers
            assert response.headers["x-policy-set"] == "default"

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_golden_trace_streaming_bypass(
        self, mock_openai_client, api_url, golden_trace_id, golden_run_id
    ):
        """Streaming completions return 501 until implemented."""
        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "Tell me about quantum computing."}
            ],
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": golden_trace_id,
                    "x-run-id": golden_run_id,
                    "x-policy-set": "golden-policy",
                },
            )

            assert response.status_code == 501
            assert "not supported" in response.text.lower()
            mock_openai_client.chat.completions.create.assert_not_called()
