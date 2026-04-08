"""Uvicorn entry: binds 127.0.0.1 by default."""

from __future__ import annotations

import os

import uvicorn

HOST = os.environ.get("MODEL_RUNTIME_HOST", "127.0.0.1")
PORT = int(os.environ.get("MODEL_RUNTIME_PORT", "8765"))


def main() -> None:
    uvicorn.run(
        "model_runtime.app:app",
        host=HOST,
        port=PORT,
        factory=False,
    )


if __name__ == "__main__":
    main()
