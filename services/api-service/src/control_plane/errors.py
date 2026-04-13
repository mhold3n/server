"""Structured contract failures aligned with `contract-error.schema.json`."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContractErrorDetail(BaseModel):
    """Single validation or policy failure."""

    path: str
    message: str
    keyword: str | None = None


class ContractValidationError(Exception):
    """Raised when a control-plane contract fails validation or policy checks."""

    def __init__(
        self,
        *,
        error_code: Literal[
            "SCHEMA_VALIDATION_FAILED",
            "LIFECYCLE_VIOLATION",
            "PROVENANCE_VIOLATION",
            "VERSION_INCOMPATIBLE",
            "LEGACY_FORBIDDEN",
        ],
        contract_type: Literal[
            "TASK_PACKET",
            "ARTIFACT_RECORD",
            "KNOWLEDGE_PACK",
            "RECIPE_OBJECT",
            "EXECUTION_ADAPTER_SPEC",
            "EVIDENCE_BUNDLE",
            "ROLE_CONTEXT_BUNDLE",
            "DECISION_LOG",
            "VERIFICATION_REPORT",
            "ESCALATION_PACKET",
            "PROBLEM_BRIEF",
            "TASK_QUEUE",
            "ENGINEERING_STATE",
            "ROUTING_POLICY",
            "BUNDLE",
        ],
        schema_id: str,
        details: list[ContractErrorDetail],
        artifact_id: str | None = None,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.contract_type = contract_type
        self.schema_id = schema_id
        self.details = details
        self.artifact_id = artifact_id

    def to_envelope(self) -> dict[str, Any]:
        """Serialize to the standard machine-readable error envelope."""
        return {
            "error_code": self.error_code,
            "contract_type": self.contract_type,
            "schema_id": self.schema_id,
            "artifact_id": self.artifact_id,
            "details": [d.model_dump(mode="json") for d in self.details],
        }


class ContractErrorEnvelope(BaseModel):
    """Pydantic mirror of contract-error.schema.json for responses."""

    error_code: str
    contract_type: str
    schema_id: str
    details: list[ContractErrorDetail] = Field(min_length=1)
    artifact_id: str | None = None
