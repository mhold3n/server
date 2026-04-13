"""Policy middleware routes for dynamic policy discovery and validation."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..policies.registry import policy_registry

logger = structlog.get_logger()

router = APIRouter(prefix="/middleware", tags=["middleware"])


class PolicyValidationRequest(BaseModel):
    """Request for policy validation."""

    content: str
    policies: list[str]
    retrieval_set: list[dict[str, Any]] | None = None
    config: dict[str, Any] | None = None


class PolicyValidationResponse(BaseModel):
    """Response from policy validation."""

    passed: bool
    overall_score: float
    policy_results: dict[str, Any]
    violations: list[str]
    suggestions: list[str]


@router.get("/registry")
async def get_policy_registry() -> dict[str, Any]:
    """Get available policies registry.

    Returns:
        Registry of available policies with schemas
    """
    try:
        policies = policy_registry.get_available_policies()
        summary = policy_registry.get_policy_summary()

        # Add schemas for each policy
        for policy in policies:
            schema = policy_registry.get_policy_schema(policy["name"])
            if schema:
                policy["schema"] = schema

        return {
            "policies": policies,
            "summary": summary,
        }

    except Exception as e:
        logger.error("Failed to get policy registry", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get policy registry"
        ) from e


@router.get("/registry/{policy_name}")
async def get_policy_info(policy_name: str) -> dict[str, Any]:
    """Get information about a specific policy.

    Args:
        policy_name: Name of the policy

    Returns:
        Policy information and schema

    Raises:
        HTTPException: If policy not found
    """
    try:
        if policy_name not in policy_registry.policies:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_name}' not found"
            )

        # Get policy info
        policies = policy_registry.get_available_policies()
        policy_info = next((p for p in policies if p["name"] == policy_name), None)

        if not policy_info:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_name}' not found"
            )

        # Get schema
        schema = policy_registry.get_policy_schema(policy_name)

        return {
            "policy": policy_info,
            "schema": schema,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get policy info", policy=policy_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get policy info") from e


@router.get("/registry/{policy_name}/schema")
async def get_policy_schema(policy_name: str) -> dict[str, Any]:
    """Get JSON schema for a specific policy.

    Args:
        policy_name: Name of the policy

    Returns:
        JSON schema for the policy

    Raises:
        HTTPException: If policy not found
    """
    try:
        schema = policy_registry.get_policy_schema(policy_name)

        if not schema:
            raise HTTPException(
                status_code=404, detail=f"Schema for policy '{policy_name}' not found"
            )

        return schema

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get policy schema", policy=policy_name, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get policy schema"
        ) from e


@router.post("/validate")
async def validate_content(
    request: PolicyValidationRequest,
) -> PolicyValidationResponse:
    """Validate content against specified policies.

    Args:
        request: Policy validation request

    Returns:
        Policy validation results

    Raises:
        HTTPException: If validation fails
    """
    try:
        policy_results = {}
        all_violations = []
        all_suggestions = []
        scores = []

        # Validate against each policy
        for policy_name in request.policies:
            if policy_name not in policy_registry.policies:
                logger.warning("Unknown policy requested", policy=policy_name)
                continue

            # Get policy instance
            policy = policy_registry.get_policy(policy_name)
            if not policy:
                logger.warning("Policy not available", policy=policy_name)
                continue

            # Apply custom config if provided
            if request.config and policy_name in request.config:
                # Update policy config temporarily
                original_config = policy_registry.policy_configs[
                    policy_name
                ].config.copy()
                policy_registry.update_policy_config(
                    policy_name, request.config[policy_name]
                )

                # Get updated policy instance
                policy = policy_registry.get_policy(policy_name)

                # Restore original config
                policy_registry.policy_configs[policy_name].config = original_config

            # Run validation
            try:
                result = await policy.validate(
                    request.content,
                    request.retrieval_set or [],
                )

                policy_results[policy_name] = {
                    "passed": result.passed,
                    "score": result.score,
                    "violations": result.violations,
                    "suggestions": result.suggestions,
                    "metadata": result.metadata,
                }

                all_violations.extend(result.violations)
                all_suggestions.extend(result.suggestions)
                scores.append(result.score)

            except Exception as e:
                logger.error(
                    "Policy validation failed", policy=policy_name, error=str(e)
                )
                policy_results[policy_name] = {
                    "passed": False,
                    "score": 0.0,
                    "violations": [f"Policy validation error: {str(e)}"],
                    "suggestions": ["Check policy configuration"],
                    "metadata": {},
                }

        # Calculate overall score
        overall_score = sum(scores) / len(scores) if scores else 0.0

        # Determine if all policies passed
        all_passed = all(result["passed"] for result in policy_results.values())

        logger.info(
            "Policy validation completed",
            policies=request.policies,
            overall_score=overall_score,
            all_passed=all_passed,
            violation_count=len(all_violations),
        )

        return PolicyValidationResponse(
            passed=all_passed,
            overall_score=overall_score,
            policy_results=policy_results,
            violations=all_violations,
            suggestions=all_suggestions,
        )

    except Exception as e:
        logger.error("Policy validation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Policy validation failed") from e


@router.post("/registry/{policy_name}/config")
async def update_policy_config(
    policy_name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Update policy configuration.

    Args:
        policy_name: Name of the policy
        config: New configuration

    Returns:
        Updated policy information

    Raises:
        HTTPException: If policy not found or update fails
    """
    try:
        if policy_name not in policy_registry.policies:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_name}' not found"
            )

        # Update config
        success = policy_registry.update_policy_config(policy_name, config)

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update policy config"
            )

        # Get updated policy info
        policy_info = policy_registry.get_available_policies()
        updated_policy = next(
            (p for p in policy_info if p["name"] == policy_name), None
        )

        logger.info("Updated policy config", policy=policy_name, config=config)

        return {
            "policy": updated_policy,
            "message": "Policy configuration updated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update policy config", policy=policy_name, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to update policy config"
        ) from e


@router.post("/registry/{policy_name}/enable")
async def enable_policy(policy_name: str) -> dict[str, Any]:
    """Enable a policy.

    Args:
        policy_name: Name of the policy

    Returns:
        Success message

    Raises:
        HTTPException: If policy not found
    """
    try:
        success = policy_registry.enable_policy(policy_name)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_name}' not found"
            )

        logger.info("Enabled policy", policy=policy_name)

        return {
            "message": f"Policy '{policy_name}' enabled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enable policy", policy=policy_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enable policy") from e


@router.post("/registry/{policy_name}/disable")
async def disable_policy(policy_name: str) -> dict[str, Any]:
    """Disable a policy.

    Args:
        policy_name: Name of the policy

    Returns:
        Success message

    Raises:
        HTTPException: If policy not found
    """
    try:
        success = policy_registry.disable_policy(policy_name)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Policy '{policy_name}' not found"
            )

        logger.info("Disabled policy", policy=policy_name)

        return {
            "message": f"Policy '{policy_name}' disabled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disable policy", policy=policy_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to disable policy") from e


@router.get("/health")
async def middleware_health() -> dict[str, Any]:
    """Check middleware health.

    Returns:
        Health status
    """
    try:
        summary = policy_registry.get_policy_summary()

        return {
            "status": "healthy",
            "service": "policy-middleware",
            "policies": summary,
        }

    except Exception as e:
        logger.error("Middleware health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "policy-middleware",
            "error": str(e),
        }
