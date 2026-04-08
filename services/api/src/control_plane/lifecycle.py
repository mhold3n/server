"""
Artifact and task_packet lifecycle transitions enforced at runtime (lifecycle gate).

For agents: illegal transitions raise ContractValidationError with LIFECYCLE_VIOLATION.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import ArtifactStatus, TaskPacketStatus
from .errors import ContractErrorDetail, ContractValidationError

if TYPE_CHECKING:
    pass

_TASK_PACKET_TRANSITIONS: dict[TaskPacketStatus, frozenset[TaskPacketStatus]] = {
    TaskPacketStatus.PENDING: frozenset(
        {TaskPacketStatus.RUNNING, TaskPacketStatus.CANCELLED},
    ),
    TaskPacketStatus.RUNNING: frozenset(
        {
            TaskPacketStatus.BLOCKED,
            TaskPacketStatus.COMPLETED,
            TaskPacketStatus.FAILED,
            TaskPacketStatus.CANCELLED,
        },
    ),
    TaskPacketStatus.BLOCKED: frozenset(
        {TaskPacketStatus.RUNNING, TaskPacketStatus.CANCELLED, TaskPacketStatus.FAILED},
    ),
    TaskPacketStatus.COMPLETED: frozenset(),
    TaskPacketStatus.FAILED: frozenset(),
    TaskPacketStatus.CANCELLED: frozenset(),
}

_ARTIFACT_TRANSITIONS: dict[ArtifactStatus, frozenset[ArtifactStatus]] = {
    ArtifactStatus.ACTIVE: frozenset(
        {ArtifactStatus.SUPERSEDED, ArtifactStatus.INVALIDATED, ArtifactStatus.ARCHIVED},
    ),
    ArtifactStatus.SUPERSEDED: frozenset({ArtifactStatus.ARCHIVED}),
    ArtifactStatus.INVALIDATED: frozenset({ArtifactStatus.ARCHIVED}),
    ArtifactStatus.ARCHIVED: frozenset(),
}


def assert_task_packet_transition(
    *,
    from_status: TaskPacketStatus,
    to_status: TaskPacketStatus,
    schema_id: str = "https://birtha.local/schemas/control-plane/v1/task-packet.schema.json",
) -> None:
    allowed = _TASK_PACKET_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ContractValidationError(
            error_code="LIFECYCLE_VIOLATION",
            contract_type="TASK_PACKET",
            schema_id=schema_id,
            details=[
                ContractErrorDetail(
                    path="/status",
                    message=f"Illegal transition {from_status!s} -> {to_status!s}",
                    keyword="lifecycle",
                )
            ],
        )


def assert_artifact_transition(
    *,
    from_status: ArtifactStatus,
    to_status: ArtifactStatus,
    schema_id: str = "https://birtha.local/schemas/control-plane/v1/artifact-record.schema.json",
) -> None:
    allowed = _ARTIFACT_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ContractValidationError(
            error_code="LIFECYCLE_VIOLATION",
            contract_type="ARTIFACT_RECORD",
            schema_id=schema_id,
            details=[
                ContractErrorDetail(
                    path="/status",
                    message=f"Illegal transition {from_status!s} -> {to_status!s}",
                    keyword="lifecycle",
                )
            ],
        )
