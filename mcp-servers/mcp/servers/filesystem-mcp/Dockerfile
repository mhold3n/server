FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install \
      fastapi>=0.104.0 \
      uvicorn[standard]>=0.24.0 \
      pydantic>=2.5.0 \
      structlog>=23.2.0 \
      aiofiles>=23.2.0 \
      pathspec>=0.11.0 \
      tree-sitter>=0.20.0 \
      tree-sitter-python>=0.20.0 \
      tree-sitter-javascript>=0.20.0 \
      tree-sitter-typescript>=0.20.0

FROM python:3.11-slim as runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY src ./src
EXPOSE 7001
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD curl -f http://localhost:7001/health || exit 1
CMD ["uvicorn","src.mcp_server:app","--host","0.0.0.0","--port","7001"]

