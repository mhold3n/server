"""End-to-end tests for WrkHrs integration."""


import pytest

from src.observability.mlflow_logger import MLflowLogger
from src.policies.evidence import EvidencePolicy
from src.wrkhrs.conditioning import RequestConditioner
from src.wrkhrs.domain_classifier import DomainClassifier
from src.wrkhrs.gateway_client import WrkHrsGatewayClient


class TestWrkHrsE2E:
    """End-to-end tests for WrkHrs integration."""

    @pytest.fixture
    async def gateway_client(self):
        """Create gateway client."""
        client = WrkHrsGatewayClient("http://localhost:8080")
        yield client
        await client.close()

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

    @pytest.mark.asyncio
    async def test_rag_workflow_with_citations(self, gateway_client, domain_classifier, conditioner, mlflow_logger, evidence_policy):
        """Test RAG workflow with citations."""
        # Classify request
        prompt = "Search for information about machine learning algorithms"
        domain = domain_classifier.classify(prompt)
        assert domain == "rag"

        # Condition request
        payload = {
            "messages": [{"role": "user", "content": prompt}]
        }
        conditioned_payload = conditioner.condition_request(domain, payload)
        assert "Always cite your sources" in conditioned_payload["messages"][0]["content"]

        # Start MLflow run
        with mlflow_logger.start_run("rag-test"):
            # Log parameters
            mlflow_logger.log_params({
                "domain": domain,
                "prompt": prompt,
                "conditioned": True
            })

            # Make request to gateway
            response = await gateway_client.chat_completion(conditioned_payload)

            # Validate response
            assert "choices" in response
            assert len(response["choices"]) > 0

            content = response["choices"][0]["message"]["content"]
            assert len(content) > 0

            # Validate evidence policy
            response_data = {
                "content": content,
                "citations": response.get("citations", [])
            }
            violations = evidence_policy.validate_response(
                response_data,
                require_evidence=True,
                min_citations=1
            )

            # Log results
            mlflow_logger.log_metrics({
                "response_length": len(content),
                "violations_count": len(violations),
                "has_citations": len(response.get("citations", [])) > 0
            })

            # Log artifacts
            mlflow_logger.log_dict(response, "response.json")
            mlflow_logger.log_dict(violations, "policy_violations.json")

            # Assertions
            assert len(violations) == 0, f"Policy violations: {violations}"

    @pytest.mark.asyncio
    async def test_tool_use_workflow(self, gateway_client, domain_classifier, conditioner, mlflow_logger):
        """Test tool use workflow."""
        # Classify request
        prompt = "Use the GitHub tool to create an issue about a bug"
        domain = domain_classifier.classify(prompt)
        assert domain == "tool_use"

        # Condition request
        payload = {
            "messages": [{"role": "user", "content": prompt}]
        }
        conditioned_payload = conditioner.condition_request(domain, payload)
        assert "Use tools to fulfill" in conditioned_payload["messages"][0]["content"]

        # Start MLflow run
        with mlflow_logger.start_run("tool-use-test"):
            # Log parameters
            mlflow_logger.log_params({
                "domain": domain,
                "prompt": prompt,
                "tools_requested": True
            })

            # Make request to gateway
            response = await gateway_client.chat_completion(conditioned_payload)

            # Validate response
            assert "choices" in response
            assert len(response["choices"]) > 0

            content = response["choices"][0]["message"]["content"]
            assert len(content) > 0

            # Log results
            mlflow_logger.log_metrics({
                "response_length": len(content),
                "tools_used": len(response.get("tool_calls", []))
            })

            # Log artifacts
            mlflow_logger.log_dict(response, "response.json")

    @pytest.mark.asyncio
    async def test_asr_workflow(self, gateway_client, domain_classifier, mlflow_logger):
        """Test ASR workflow."""
        # Classify request
        prompt = "Transcribe this audio file"
        domain = domain_classifier.classify(prompt, {"audio": "test.wav"})
        assert domain == "asr"

        # Start MLflow run
        with mlflow_logger.start_run("asr-test"):
            # Log parameters
            mlflow_logger.log_params({
                "domain": domain,
                "audio_file": "test.wav"
            })

            # Make request to ASR service
            response = await gateway_client.get_asr_transcription("test.wav")

            # Validate response
            assert "transcription" in response
            assert "confidence" in response

            transcription = response["transcription"]
            confidence = response["confidence"]

            assert len(transcription) > 0
            assert 0 <= confidence <= 1

            # Log results
            mlflow_logger.log_metrics({
                "transcription_length": len(transcription),
                "confidence": confidence
            })

            # Log artifacts
            mlflow_logger.log_dict(response, "asr_response.json")

    @pytest.mark.asyncio
    async def test_policy_enforcement_workflow(self, gateway_client, evidence_policy, mlflow_logger):
        """Test policy enforcement workflow."""
        # Start MLflow run
        with mlflow_logger.start_run("policy-test"):
            # Test response without citations
            response_without_citations = {
                "content": "This is a fact without any citations or evidence.",
                "citations": []
            }

            violations = evidence_policy.validate_response(
                response_without_citations,
                require_evidence=True,
                min_citations=1
            )

            # Log results
            mlflow_logger.log_metrics({
                "violations_count": len(violations),
                "has_citations": False
            })

            # Log artifacts
            mlflow_logger.log_dict(violations, "policy_violations.json")

            # Assertions
            assert len(violations) > 0
            assert "requires evidence/citations" in violations[0]

    @pytest.mark.asyncio
    async def test_github_workflow_integration(self, gateway_client, mlflow_logger):
        """Test GitHub workflow integration."""
        # Start MLflow run
        with mlflow_logger.start_run("github-workflow-test"):
            # Test code-related prompt
            prompt = "Create a GitHub issue for a bug in the authentication system"

            # Log parameters
            mlflow_logger.log_params({
                "prompt": prompt,
                "workflow": "github",
                "action": "create_issue"
            })

            # Make request to gateway
            response = await gateway_client.chat_completion({
                "messages": [{"role": "user", "content": prompt}]
            })

            # Validate response
            assert "choices" in response
            assert len(response["choices"]) > 0

            content = response["choices"][0]["message"]["content"]
            assert len(content) > 0

            # Log results
            mlflow_logger.log_metrics({
                "response_length": len(content),
                "workflow_detected": "github" in content.lower()
            })

            # Log artifacts
            mlflow_logger.log_dict(response, "github_workflow_response.json")

    @pytest.mark.asyncio
    async def test_full_system_health_check(self, gateway_client, mlflow_logger):
        """Test full system health check."""
        # Start MLflow run
        with mlflow_logger.start_run("health-check-test"):
            # Test gateway health
            try:
                # This would be a health check endpoint if implemented
                # For now, we'll test the tool registry
                tools = await gateway_client.get_tool_registry()

                # Log results
                mlflow_logger.log_metrics({
                    "tools_available": len(tools.get("tools", [])),
                    "gateway_healthy": True
                })

                # Log artifacts
                mlflow_logger.log_dict(tools, "tool_registry.json")

                # Assertions
                assert "tools" in tools
                assert len(tools["tools"]) > 0

            except Exception as e:
                # Log error
                mlflow_logger.log_metrics({
                    "gateway_healthy": False,
                    "error": str(e)
                })

                # Re-raise for test failure
                raise

    @pytest.mark.asyncio
    async def test_mlflow_provenance_tracking(self, mlflow_logger):
        """Test MLflow provenance tracking."""
        # Test multiple runs
        run_ids = []

        for i in range(3):
            with mlflow_logger.start_run(f"provenance-test-{i}"):
                run_id = mlflow_logger.active_run_id()
                run_ids.append(run_id)

                # Log parameters
                mlflow_logger.log_params({
                    "test_id": i,
                    "timestamp": f"2024-01-{i+1:02d}T00:00:00Z"
                })

                # Log metrics
                mlflow_logger.log_metrics({
                    "accuracy": 0.9 + (i * 0.01),
                    "latency": 100 + (i * 10)
                })

                # Log artifacts
                mlflow_logger.log_dict({
                    "test_data": f"sample_data_{i}",
                    "results": f"results_{i}"
                }, f"test_results_{i}.json")

        # Verify all runs were created
        assert len(run_ids) == 3
        assert all(run_id is not None for run_id in run_ids)
        assert len(set(run_ids)) == 3  # All unique

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, gateway_client, mlflow_logger):
        """Test error handling and recovery."""
        # Start MLflow run
        with mlflow_logger.start_run("error-handling-test"):
            # Test with invalid request
            try:
                await gateway_client.chat_completion({
                    "invalid": "request"
                })

                # If we get here, log the unexpected success
                mlflow_logger.log_metrics({
                    "error_handled": False,
                    "unexpected_success": True
                })

            except Exception as e:
                # Log the expected error
                mlflow_logger.log_metrics({
                    "error_handled": True,
                    "error_type": type(e).__name__
                })

                # Log error details
                mlflow_logger.log_dict({
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "error_details.json")

                # This is expected behavior
                assert "invalid" in str(e).lower() or "request" in str(e).lower()

    @pytest.mark.asyncio
    async def test_performance_metrics(self, gateway_client, mlflow_logger):
        """Test performance metrics collection."""
        import time

        # Start MLflow run
        with mlflow_logger.start_run("performance-test"):
            # Measure response time
            start_time = time.time()

            try:
                response = await gateway_client.chat_completion({
                    "messages": [{"role": "user", "content": "Test performance"}]
                })

                end_time = time.time()
                response_time = end_time - start_time

                # Log performance metrics
                mlflow_logger.log_metrics({
                    "response_time": response_time,
                    "success": True
                })

                # Log artifacts
                mlflow_logger.log_dict({
                    "response_time": response_time,
                    "response_size": len(str(response))
                }, "performance_metrics.json")

                # Assertions
                assert response_time < 30.0  # Should respond within 30 seconds
                assert "choices" in response

            except Exception as e:
                end_time = time.time()
                response_time = end_time - start_time

                # Log error metrics
                mlflow_logger.log_metrics({
                    "response_time": response_time,
                    "success": False,
                    "error": str(e)
                })

                # Re-raise for test failure
                raise











