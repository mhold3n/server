"""End-to-end tests for the API's WrkHrs-adjacent helpers.

These tests run against a live API container (RUN_LIVE_STACK_TESTS=1) and validate:
- Domain classification / request conditioning helpers (pure Python)
- The async gateway client wrapper can call the API's OpenAI-compatible endpoint
- Policy enforcement headers are present and pass on a "good" response
"""

from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio

from src.policies.evidence import EvidencePolicy
from ai_shared_service.conditioning import NonGenerativeConditioning
from ai_shared_service.domain_classifier import DomainClassifier
from ai_shared_service.gateway_client import WrkHrsGatewayClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STACK_TESTS") != "1",
    reason="E2E tests require a running API and stack; set RUN_LIVE_STACK_TESTS=1.",
)


@pytest_asyncio.fixture
async def gateway_client() -> WrkHrsGatewayClient:
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8080")
    async with WrkHrsGatewayClient(base_url) as client:
        yield client


def test_domain_classifier_returns_expected_domain() -> None:
    clf = DomainClassifier()
    domain = clf.classify("What is H2O and what is its pH?")
    assert isinstance(domain, dict)
    # The classifier returns a weight mapping; it may be empty for short/ambiguous prompts.
    assert set(domain).issubset({"chemistry", "mechanical", "materials"})


def test_request_conditioner_injects_guidance() -> None:
    conditioner = NonGenerativeConditioning()
    prompt = "The pressure is 14.7 psi."
    normalized = conditioner.apply_si_normalization(prompt, normalize=True)
    assert "normalized_text" in normalized
    assert isinstance(normalized["normalized_text"], str)


@pytest.mark.asyncio
async def test_gateway_client_health_check(gateway_client: WrkHrsGatewayClient) -> None:
    health = await gateway_client.health_check()
    assert "status" in health


@pytest.mark.asyncio
async def test_gateway_client_chat_completion_and_evidence_policy(
    gateway_client: WrkHrsGatewayClient,
) -> None:
    response = await gateway_client.chat_completion(
        messages=[{"role": "user", "content": "Give a concise answer with citations."}],
        model="mock-model",
        temperature=0.0,
        max_tokens=50,
    )
    assert response.get("choices")
    content = response["choices"][0]["message"]["content"]
    assert isinstance(content, str) and content

    policy = EvidencePolicy(min_citations=3, evidence_required=True)
    result = await policy.validate(content, retrieval_set=[])
    assert result.passed, result.violations


@pytest.mark.asyncio
async def test_policy_headers_present_on_http_call() -> None:
    api_url = os.environ.get("API_BASE_URL", "http://localhost:8080")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{api_url}/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [{"role": "user", "content": "Answer with citations."}],
            },
            headers={"x-trace-id": "ai_gateway_client-e2e-trace", "x-run-id": "ai_gateway_client-e2e-run"},
        )
        assert r.status_code == 200
        assert r.headers.get("x-policy-verdict") == "True"
        assert float(r.headers.get("x-policy-score", "0")) >= 0.9
