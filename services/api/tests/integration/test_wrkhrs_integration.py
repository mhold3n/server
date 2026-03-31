"""Integration tests for WrkHrs-related components (in-process; no live stack)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.observability.mlflow_logger import (
    EnvironmentSnapshot,
    MLflowLogger,
    RunSpec,
)
from src.policies.evidence import EvidencePolicy
from src.wrkhrs.conditioning import NonGenerativeConditioning, RequestConditioner
from src.wrkhrs.domain_classifier import DomainClassifier
from src.wrkhrs.gateway_client import WrkHrsGatewayClient


class TestWrkHrsIntegration:
    """WrkHrs integration tests against current library behavior."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def gateway_client(self) -> AsyncMock:
        return AsyncMock(spec=WrkHrsGatewayClient)

    @pytest.fixture
    def domain_classifier(self) -> DomainClassifier:
        return DomainClassifier()

    @pytest.fixture
    def conditioner(self) -> NonGenerativeConditioning:
        return NonGenerativeConditioning()

    @pytest.fixture
    def evidence_policy(self) -> EvidencePolicy:
        return EvidencePolicy(min_citations=3, source_quotas={})

    def test_domain_classifier_returns_chemistry_scores(
        self, domain_classifier: DomainClassifier
    ) -> None:
        text = (
            "The reaction equilibrium catalyst uses molarity, pH, and oxidation "
            "reduction in the synthesis process."
        )
        scores = domain_classifier.classify(text)
        assert "chemistry" in scores
        # get_primary_domain defaults to threshold=0.3; raw scores can be below that gate
        primary = domain_classifier.get_primary_domain(text, threshold=0.1)
        assert primary == "chemistry"

    def test_request_conditioner_domain_weighting(
        self, conditioner: NonGenerativeConditioning
    ) -> None:
        weights = {"chemistry": 0.7, "mechanical": 0.2, "materials": 0.1}
        out = conditioner.apply_domain_weighting("What is the bond energy?", weights)
        assert "system_context" in out
        assert "chemistry" in out["system_context"].lower()

    def test_request_conditioner_alias(self) -> None:
        assert RequestConditioner is NonGenerativeConditioning

    @pytest.mark.asyncio
    async def test_gateway_client_chat_completion(
        self, gateway_client: AsyncMock
    ) -> None:
        mock_response = {"choices": [{"message": {"content": "Test response"}}]}
        gateway_client.chat_completion.return_value = mock_response
        messages = [{"role": "user", "content": "Hello"}]
        response = await gateway_client.chat_completion(messages)
        assert response == mock_response
        gateway_client.chat_completion.assert_called_once()
        args, kwargs = gateway_client.chat_completion.call_args
        assert args[0] == messages or kwargs.get("messages") == messages

    @pytest.mark.asyncio
    async def test_gateway_client_domain_classify(
        self, gateway_client: AsyncMock
    ) -> None:
        gateway_client.domain_classify.return_value = {"domains": {"chemistry": 1.0}}
        out = await gateway_client.domain_classify("bond energy")
        assert out["domains"]["chemistry"] == 1.0

    @pytest.mark.asyncio
    async def test_evidence_policy_validate_passes_with_diverse_sources(
        self, evidence_policy: EvidencePolicy
    ) -> None:
        output = "Statement one [1] two [2] three [3]."
        retrieval = [
            {"metadata": {"source_type": "paper"}},
            {"metadata": {"source_type": "textbook"}},
            {"metadata": {"source_type": "journal"}},
        ]
        result = await evidence_policy.validate(output, retrieval)
        assert result.passed
        assert not result.violations

    @pytest.mark.asyncio
    async def test_mlflow_log_run_short_circuits_without_experiment(self) -> None:
        logger = MLflowLogger(tracking_uri="http://127.0.0.1:9")
        logger.experiment_id = None
        env = EnvironmentSnapshot(
            timestamp=datetime.utcnow(),
            service_version="0.1.0",
            model_version="test",
            config_hash="abc",
            dependencies={},
        )
        run_id = await logger.log_run(
            RunSpec(prompt="hi", model="m"),
            [],
            "raw",
            "post",
            [],
            env,
        )
        assert run_id == "no-mlflow"

    def test_health_endpoint(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("healthy", "degraded")
        assert "services" in body

    def test_feedback_endpoint_with_provenance_mock(self, client: TestClient) -> None:
        mock_logger = MagicMock()
        with patch("src.app.provenance_logger", mock_logger):
            response = client.post(
                "/v1/feedback",
                json={
                    "run_id": "test-run-id",
                    "rating": 5,
                    "reasons": ["great"],
                    "notes": "ok",
                },
            )
        assert response.status_code == 200
        assert response.json().get("status") == "success"
        mock_logger.log_feedback.assert_called_once()
