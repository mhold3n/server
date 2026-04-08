"""
Control-plane contracts: JSON Schema-backed task packets, typed artifacts, and validation.

For agents: authoritative shapes live under repo `schemas/control-plane/v1/`; this package
provides Pydantic mirrors, lifecycle helpers, and runtime validation for API write paths.
"""

from .contracts import TaskPacket
from .errors import ContractValidationError

__all__ = ["ContractValidationError", "TaskPacket"]
