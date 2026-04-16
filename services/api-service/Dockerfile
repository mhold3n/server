# Build from repository root (see docker-compose.yml: context: .).
# Workspace deps (ai-shared-service, domain-*, response-control-framework, …) are
# local packages; pip install on api-service alone cannot resolve them — use uv sync.
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_EDITABLE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY services ./services
COPY schemas ./schemas
COPY knowledge ./knowledge

RUN uv sync --frozen --python 3.11 --package agent-orchestrator-api --no-dev --no-editable

FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /build/.venv /opt/venv

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY services/api-service/src/ ./src/
COPY schemas/ ./schemas/
COPY knowledge/ ./knowledge/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use python -m uvicorn: entrypoint scripts in copied .venv can break across stages.
CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]
