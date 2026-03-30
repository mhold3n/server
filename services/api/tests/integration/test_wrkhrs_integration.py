"""Integration tests for WrkHrs integration."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.observability.mlflow_logger import MLflowLogger
from src.policies.evidence import EvidencePolicy
from src.wrkhrs.conditioning import RequestConditioner
from src.wrkhrs.domain_classifier import DomainClassifier
from src.wrkhrs.gateway_client import WrkHrsGatewayClient


class TestWrkHrsIntegration:
    """Test WrkHrs integration components."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def gateway_client(self):
        """Create mock gateway client."""
        return AsyncMock(spec=WrkHrsGatewayClient)

    @pytest.fixture
    def domain_classifier(self):
        """Create domain classifier."""
        return DomainClassifier()

    @pytest.fixture
    def conditioner(self):
        """Create request conditioner."""
        return RequestConditioner()

    @pytest.fixture
    def mlflow_logger(self):
        """Create MLflow logger."""
        return MLflowLogger()

    @pytest.fixture
    def evidence_policy(self):
        """Create evidence policy."""
        return EvidencePolicy()

    def test_domain_classification(self, domain_classifier):
        """Test domain classification."""
        # Test RAG domain
        rag_prompt = "Search for information about machine learning"
        domain = domain_classifier.classify(rag_prompt)
        assert domain == "rag"

        # Test tool use domain
        tool_prompt = "Use the GitHub tool to create an issue"
        domain = domain_classifier.classify(tool_prompt)
        assert domain == "tool_use"

        # Test ASR domain
        asr_prompt = "Transcribe this audio file"
        domain = domain_classifier.classify(asr_prompt, {"audio": "test.wav"})
        assert domain == "asr"

        # Test general domain
        general_prompt = "Hello, how are you?"
        domain = domain_classifier.classify(general_prompt)
        assert domain == "general"

    def test_request_conditioning(self, conditioner):
        """Test request conditioning."""
        # Test RAG conditioning
        rag_payload = {"messages": [{"role": "user", "content": "Search for ML info"}]}
        conditioned = conditioner.condition_request("rag", rag_payload)
        assert "Always cite your sources" in conditioned["messages"][0]["content"]

        # Test tool use conditioning
        tool_payload = {"messages": [{"role": "user", "content": "Use tools to help"}]}
        conditioned = conditioner.condition_request("tool_use", tool_payload)
        assert "Use tools to fulfill" in conditioned["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_gateway_client_chat_completion(self, gateway_client):
        """Test gateway client chat completion."""
        # Mock response
        mock_response = {"choices": [{"message": {"content": "Test response"}}]}
        gateway_client.chat_completion.return_value = mock_response

        # Test chat completion
        payload = {"messages": [{"role": "user", "content": "Hello"}]}
        response = await gateway_client.chat_completion(payload)

        assert response == mock_response
        gateway_client.chat_completion.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_gateway_client_tool_registry(self, gateway_client):
        """Test gateway client tool registry."""
        # Mock response
        mock_response = {
            "tools": [
                {"name": "github", "description": "GitHub operations"},
                {"name": "filesystem", "description": "File operations"},
            ]
        }
        gateway_client.get_tool_registry.return_value = mock_response

        # Test tool registry
        response = await gateway_client.get_tool_registry()

        assert response == mock_response
        gateway_client.get_tool_registry.assert_called_once()

    @pytest.mark.asyncio
    async def test_gateway_client_asr_transcription(self, gateway_client):
        """Test gateway client ASR transcription."""
        # Mock response
        mock_response = {"transcription": "Hello world", "confidence": 0.95}
        gateway_client.get_asr_transcription.return_value = mock_response

        # Test ASR transcription
        response = await gateway_client.get_asr_transcription("test.wav")

        assert response == mock_response
        gateway_client.get_asr_transcription.assert_called_once_with("test.wav")

    def test_evidence_policy_validation(self, evidence_policy):
        """Test evidence policy validation."""
        # Test response with citations
        response_with_citations = {
            "content": "This is a fact [1] and another fact [2].",
            "citations": [
                {"url": "https://example.com", "text": "Source 1"},
                {"url": "https://example2.com", "text": "Source 2"},
            ],
        }
        violations = evidence_policy.validate_response(
            response_with_citations, require_evidence=True, min_citations=2
        )
        assert len(violations) == 0

        # Test response without citations
        response_without_citations = {
            "content": "This is a fact without citations.",
            "citations": [],
        }
        violations = evidence_policy.validate_response(
            response_without_citations, require_evidence=True, min_citations=1
        )
        assert len(violations) > 0
        assert "requires evidence/citations" in violations[0]

    def test_evidence_policy_inline_citations(self, evidence_policy):
        """Test evidence policy with inline citations."""
        # Test response with inline citations
        response_with_inline = {
            "content": "This is a fact [1] and another fact (Source 2).",
            "citations": [],
        }
        violations = evidence_policy.validate_response(
            response_with_inline, require_evidence=True, min_citations=1
        )
        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_mlflow_logging(self, mlflow_logger):
        """Test MLflow logging."""
        with patch("mlflow.start_run") as mock_start_run, patch(
            "mlflow.end_run"
        ) as mock_end_run, patch("mlflow.log_params") as mock_log_params, patch(
            "mlflow.log_metrics"
        ) as mock_log_metrics:

            # Mock active run
            mock_run = AsyncMock()
            mock_run.info.run_id = "test-run-id"
            mock_start_run.return_value = mock_run

            # Test logging
            with mlflow_logger.start_run("test-run"):
                mlflow_logger.log_params({"param1": "value1"})
                mlflow_logger.log_metrics({"metric1": 0.95})
                mlflow_logger.end_run()

            mock_start_run.assert_called_once()
            mock_end_run.assert_called_once()
            mock_log_params.assert_called_once_with({"param1": "value1"})
            mock_log_metrics.assert_called_once_with({"metric1": 0.95})

    def test_health_check_endpoints(self, client):
        """Test health check endpoints."""
        # Test main health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # Test WrkHrs health endpoint
        response = client.get("/health/wrkhrs")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_full_workflow_integration(self, client, gateway_client):
        """Test full workflow integration."""
        with patch(
            "src.wrkhrs.gateway_client.WrkHrsGatewayClient"
        ) as mock_client_class:
            # Mock client instance
            mock_client_class.return_value = gateway_client

            # Mock gateway response
            mock_response = {
                "choices": [
                    {"message": {"content": "Test response with citations [1]"}}
                ]
            }
            gateway_client.chat_completion.return_value = mock_response

            # Test chat completion endpoint
            response = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Search for ML information"}
                    ],
                    "domain": "rag",
                },
            )

            assert response.status_code == 200
            assert "Test response" in response.json()["content"]

    def test_policy_middleware_integration(self, client):
        """Test policy middleware integration."""
        # Test policy registry endpoint
        response = client.get("/v1/middleware/policies")
        assert response.status_code == 200
        policies = response.json()
        assert "evidence" in policies
        assert "citations" in policies
        assert "hedging" in policies
        assert "units" in policies

    def test_feedback_system_integration(self, client):
        """Test feedback system integration."""
        # Test feedback submission
        feedback_data = {
            "run_id": "test-run-id",
            "rating": 5,
            "reason": "Excellent response",
            "suggestions": "None",
        }

        response = client.post("/v1/feedback", json=feedback_data)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_mcp_registry_integration(self, client):
        """Test MCP registry integration."""
        # Test MCP listing
        response = client.get("/v1/mcps")
        assert response.status_code == 200
        mcps = response.json()
        assert len(mcps) > 0

        # Test specific MCP details
        response = client.get("/v1/mcps/github-mcp")
        assert response.status_code == 200
        mcp_info = response.json()
        assert mcp_info["name"] == "github-mcp"
        assert mcp_info["type"] == "tool"

    def test_observability_integration(self, client):
        """Test observability integration."""
        # Test tracing headers
        response = client.get("/health", headers={"X-Trace-Id": "test-trace-id"})
        assert response.status_code == 200

        # Test metrics endpoint
        response = client.get("/metrics")
        assert response.status_code == 200
