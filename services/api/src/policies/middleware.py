"""Policy enforcement middleware for aggregating verdicts from all enabled policies."""

from typing import Any

import structlog
from pydantic import BaseModel

from .evidence import PolicyResult
from .registry import policy_registry

logger = structlog.get_logger()


class PolicyVerdict(BaseModel):
    """Aggregated policy verdict for a request."""

    overall_passed: bool
    overall_score: float
    total_violations: int
    total_suggestions: int
    policy_results: dict[str, PolicyResult]
    metadata: dict[str, Any] = {}


class PolicyEnforcer:
    """Enforces all enabled policies against output and aggregates verdicts."""

    def __init__(self):
        """Initialize policy enforcer."""
        self.registry = policy_registry

    async def validate(
        self,
        output: str,
        retrieval_docs: list[dict[str, Any]] | None = None,
        policy_set: str = "default",
    ) -> PolicyVerdict:
        """Validate output against all enabled policies.

        Args:
            output: Generated output text
            retrieval_docs: Retrieved documents for context
            policy_set: Policy set to use (for future policy sets)

        Returns:
            Aggregated policy verdict
        """
        enabled_policies = self.registry.get_enabled_policies()
        policy_results = {}
        total_violations = 0
        total_suggestions = 0
        scores = []

        logger.info(
            "Running policy validation",
            output_length=len(output),
            retrieval_count=len(retrieval_docs) if retrieval_docs else 0,
            enabled_policies=enabled_policies,
        )

        # Run each enabled policy
        for policy_name in enabled_policies:
            try:
                policy = self.registry.get_policy(policy_name)
                if not policy:
                    logger.warning("Policy not found", policy_name=policy_name)
                    continue

                # Run policy validation
                result = await policy.validate(output, retrieval_docs)
                policy_results[policy_name] = result

                # Aggregate metrics
                total_violations += len(result.violations)
                total_suggestions += len(result.suggestions)
                scores.append(result.score)

                logger.info(
                    "Policy validation completed",
                    policy_name=policy_name,
                    passed=result.passed,
                    score=result.score,
                    violations=len(result.violations),
                )

            except Exception as e:
                logger.error(
                    "Policy validation failed",
                    policy_name=policy_name,
                    error=str(e),
                )
                # Create failed result
                failed_result = PolicyResult(
                    passed=False,
                    score=0.0,
                    violations=[f"Policy validation error: {str(e)}"],
                    suggestions=["Fix policy configuration"],
                    metadata={"error": str(e)},
                )
                policy_results[policy_name] = failed_result
                total_violations += 1
                scores.append(0.0)

        # Calculate overall metrics
        overall_passed = all(result.passed for result in policy_results.values())
        overall_score = sum(scores) / len(scores) if scores else 0.0

        # Create metadata
        metadata = {
            "policy_count": len(enabled_policies),
            "policy_names": enabled_policies,
            "scores": {name: result.score for name, result in policy_results.items()},
            "violation_counts": {
                name: len(result.violations) for name, result in policy_results.items()
            },
        }

        verdict = PolicyVerdict(
            overall_passed=overall_passed,
            overall_score=overall_score,
            total_violations=total_violations,
            total_suggestions=total_suggestions,
            policy_results=policy_results,
            metadata=metadata,
        )

        logger.info(
            "Policy validation completed",
            overall_passed=overall_passed,
            overall_score=overall_score,
            total_violations=total_violations,
            total_suggestions=total_suggestions,
        )

        return verdict

    def get_policy_summary(self) -> dict[str, Any]:
        """Get summary of available policies.

        Returns:
            Policy summary information
        """
        return self.registry.get_policy_summary()

    def get_enabled_policies(self) -> list[str]:
        """Get list of enabled policy names.

        Returns:
            List of enabled policy names
        """
        return self.registry.get_enabled_policies()

    def enable_policy(self, name: str) -> bool:
        """Enable a policy.

        Args:
            name: Policy name

        Returns:
            True if successful, False otherwise
        """
        return self.registry.enable_policy(name)

    def disable_policy(self, name: str) -> bool:
        """Disable a policy.

        Args:
            name: Policy name

        Returns:
            True if successful, False otherwise
        """
        return self.registry.disable_policy(name)


# Global policy enforcer instance
policy_enforcer = PolicyEnforcer()
