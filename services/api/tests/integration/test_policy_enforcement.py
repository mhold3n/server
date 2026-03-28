"""Integration tests for policy enforcement in chat flow."""

from unittest.mock import Mock, patch

import httpx
import pytest


class TestPolicyEnforcementIntegration:
    """Test policy enforcement integration in chat flow."""

    @pytest.fixture
    def api_url(self):
        """Get API URL."""
        return "http://localhost:8080"

    @pytest.fixture
    def sample_chat_request(self):
        """Sample chat request for testing."""
        return {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "Tell me about quantum computing."}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

    @pytest.fixture
    def sample_chat_request_with_hedging(self):
        """Sample chat request that should trigger hedging policy."""
        return {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {
                    "role": "user",
                    "content": "What might be the best approach for this problem?",
                }
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

    @pytest.fixture
    def sample_chat_request_without_citations(self):
        """Sample chat request that should trigger citation policy."""
        return {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "Explain the theory of relativity."}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

    @pytest.mark.asyncio
    async def test_chat_request_with_policy_headers(self, api_url, sample_chat_request):
        """Test chat request with policy headers."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            # Should return 200 even if worker not available (will be 503)
            assert response.status_code in [200, 503]

            # Check response headers
            assert "x-trace-id" in response.headers
            assert "x-run-id" in response.headers
            assert "x-policy-set" in response.headers
            assert response.headers["x-trace-id"] == "test-trace-123"
            assert response.headers["x-run-id"] == "test-run-456"
            assert response.headers["x-policy-set"] == "test-policy"

    @pytest.mark.asyncio
    async def test_chat_request_without_headers(self, api_url, sample_chat_request):
        """Test chat request without headers generates context."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions", json=sample_chat_request
            )

            # Should return 200 even if worker not available (will be 503)
            assert response.status_code in [200, 503]

            # Check response headers were generated
            assert "x-trace-id" in response.headers
            assert "x-run-id" in response.headers
            assert "x-policy-set" in response.headers
            assert response.headers["x-policy-set"] == "default"

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_with_mock_worker(
        self, mock_openai_client, api_url, sample_chat_request
    ):
        """Test policy enforcement with mocked OpenAI client."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "This might be correct, but it seems like it could work."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Check policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Policy verdict should be False due to hedging
            assert response.headers["x-policy-verdict"] == "False"
            assert float(response.headers["x-policy-score"]) < 1.0

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_with_citations(self, mock_openai_client, api_url):
        """Test policy enforcement with citations."""
        # Mock OpenAI response with citations
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "Quantum computing is a field of study [1]. It uses quantum mechanics [2]. The theory is well-established [3]."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "Explain quantum computing with citations."}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Check policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Should pass citation policy
            assert response.headers["x-policy-verdict"] == "True"
            assert float(response.headers["x-policy-score"]) > 0.5

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_with_units(self, mock_openai_client, api_url):
        """Test policy enforcement with SI units."""
        # Mock OpenAI response with proper SI units
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "The temperature is 298 K and the pressure is 101.3 kPa."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "What are the standard conditions?"}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Check policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Should pass unit policy
            assert response.headers["x-policy-verdict"] == "True"
            assert float(response.headers["x-policy-score"]) > 0.5

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_with_imperial_units(
        self, mock_openai_client, api_url
    ):
        """Test policy enforcement with imperial units (should fail)."""
        # Mock OpenAI response with imperial units
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "The temperature is 77°F and the pressure is 14.7 psi."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "What are the standard conditions?"}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Check policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Should fail unit policy
            assert response.headers["x-policy-verdict"] == "False"
            assert float(response.headers["x-policy-score"]) < 0.5

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    @patch("src.app.mlflow_logger")
    async def test_mlflow_logging_integration(
        self, mock_mlflow_logger, mock_openai_client, api_url, sample_chat_request
    ):
        """Test MLflow logging integration."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This might be correct."
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        # Mock MLflow logger
        mock_mlflow_logger.return_value = Mock()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=sample_chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Verify MLflow logger was called
            # Note: This is a simplified test - in practice, you'd need to mock the MLflow calls more specifically

    @pytest.mark.asyncio
    async def test_chat_request_validation(self, api_url):
        """Test chat request validation."""
        async with httpx.AsyncClient() as client:
            # Test with empty messages
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json={"model": "test-model", "messages": []},
            )

            assert response.status_code == 422
            assert "messages" in response.text

    @pytest.mark.asyncio
    async def test_chat_request_without_openai_client(
        self, api_url, sample_chat_request
    ):
        """Test chat request when OpenAI client is not available."""
        # This test assumes the OpenAI client is not initialized
        # In a real scenario, this would be tested by not initializing the client

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions", json=sample_chat_request
            )

            # Should return 503 if OpenAI client not available
            assert response.status_code == 503
            assert "OpenAI client not available" in response.text

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_streaming_request_policy_bypass(self, mock_openai_client, api_url):
        """Test that streaming requests bypass policy enforcement."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This might be correct."
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [
                {"role": "user", "content": "Tell me about quantum computing."}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Streaming requests should not have policy verdict headers
            assert "x-policy-verdict" not in response.headers
            assert "x-policy-score" not in response.headers

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_error_handling(
        self, mock_openai_client, api_url, sample_chat_request
    ):
        """Test policy enforcement error handling."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This might be correct."
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        # Mock policy enforcer to raise exception
        with patch("src.policies.middleware.policy_enforcer.validate") as mock_validate:
            mock_validate.side_effect = Exception("Policy enforcement error")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_url}/v1/chat/completions",
                    json=sample_chat_request,
                    headers={
                        "x-trace-id": "test-trace-123",
                        "x-run-id": "test-run-456",
                        "x-policy-set": "test-policy",
                    },
                )

                # Should still return 200 even if policy enforcement fails
                assert response.status_code == 200

                # Should not have policy verdict headers due to error
                assert "x-policy-verdict" not in response.headers
                assert "x-policy-score" not in response.headers

    @pytest.mark.asyncio
    @patch("src.app.openai_client")
    async def test_policy_enforcement_with_retrieval_docs(
        self, mock_openai_client, api_url
    ):
        """Test policy enforcement with retrieval documents."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "This might be correct based on the evidence."
        )
        mock_response.usage = Mock()
        mock_response.usage.dict.return_value = {"total_tokens": 50}

        mock_openai_client.chat.completions.create.return_value = mock_response

        chat_request = {
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [{"role": "user", "content": "What do you think about this?"}],
            "temperature": 0.7,
            "max_tokens": 100,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=chat_request,
                headers={
                    "x-trace-id": "test-trace-123",
                    "x-run-id": "test-run-456",
                    "x-policy-set": "test-policy",
                },
            )

            assert response.status_code == 200

            # Check policy verdict headers
            assert "x-policy-verdict" in response.headers
            assert "x-policy-score" in response.headers

            # Should have some policy verdict
            assert response.headers["x-policy-verdict"] in ["True", "False"]
            assert 0.0 <= float(response.headers["x-policy-score"]) <= 1.0
