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
      qdrant-client>=1.7.0 \
      numpy>=1.24.0

FROM python:3.11-slim as runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY src ./src
EXPOSE 7003
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD curl -f http://localhost:7003/health || exit 1
ENV QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
CMD ["uvicorn","src.vector_server:app","--host","0.0.0.0","--port","7003"]
