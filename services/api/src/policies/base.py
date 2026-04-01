from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .evidence import PolicyResult


class BasePolicy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def validate(
        self,
        output: str,
        retrieval_docs: list[dict[str, Any]] | None = None,
    ) -> PolicyResult:
        raise NotImplementedError

