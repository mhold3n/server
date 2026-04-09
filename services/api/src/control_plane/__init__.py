"""
Control-plane contracts: JSON Schema-backed task packets, typed artifacts, and validation.

For agents: authoritative shapes live under repo `schemas/control-plane/v1/`; this package
provides Pydantic mirrors, lifecycle helpers, and runtime validation for API write paths.
"""

from .contracts import TaskPacket
from .errors import ContractValidationError
from .knowledge_pool import (
    compile_role_context,
    load_knowledge_pool,
    load_minutes_inventory,
    resolve_runtime,
    resolve_stack,
    verify_runtime,
)

__all__ = [
    "ContractValidationError",
    "TaskPacket",
    "load_knowledge_pool",
    "load_minutes_inventory",
    "resolve_stack",
    "resolve_runtime",
    "verify_runtime",
    "compile_role_context",
]
