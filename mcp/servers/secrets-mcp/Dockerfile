FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates unzip && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./

# Build-time venv to keep runtime layer small.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install \
      mcp>=0.1.0 \
      fastapi>=0.104.0 \
      uvicorn[standard]>=0.24.0 \
      pydantic>=2.5.0 \
      structlog>=23.2.0 \
      cryptography>=41.0.0 \
      python-dotenv>=1.0.0 \
      httpx>=0.25.0

FROM python:3.11-slim as runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates unzip && rm -rf /var/lib/apt/lists/*

# Install Bitwarden Secrets Manager CLI (bws). The install script drops the binary under
# /root/.local/bin, which is not on the default slim PATH — add it before COPY so runtime
# subprocesses (uvicorn -> BitwardenSmClient) can exec `bws`.
RUN curl -fsSL https://bws.bitwarden.com/install | sh \
    && test -x /root/.local/bin/bws \
    && /root/.local/bin/bws --version

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/root/.local/bin:/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WORKDIR /app
COPY src ./src

EXPOSE 7002
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD curl -f http://localhost:7002/health || exit 1

CMD ["uvicorn","src.secrets_server:app","--host","0.0.0.0","--port","7002"]

