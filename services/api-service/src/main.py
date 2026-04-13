"""ASGI entry re-export for `uvicorn src.main:app` and tests that import `src.main`."""

from src.app import app

__all__ = ["app"]
