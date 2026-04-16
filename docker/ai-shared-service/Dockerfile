# Build the optional LangChain/Haystack sidecar from the standalone Git repo (no in-tree copy).
# Tag must match ``[tool.uv.sources]`` / ``DOMAIN_PACKAGES_TAG`` in the server root ``pyproject.toml``.
FROM python:3.11-slim

ARG AI_SHARED_GIT_URL=https://github.com/mhold3n/ai-shared-service.git
ARG AI_SHARED_TAG=v0.1.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth 1 --branch "${AI_SHARED_TAG}" "${AI_SHARED_GIT_URL}" .

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8090

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8090"]
