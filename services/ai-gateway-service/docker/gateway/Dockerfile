FROM python:3.11-slim

WORKDIR /app

# Build context is services/ai-gateway-service/, so the live gateway source is
# under services/gateway/ within that subtree.

# sentence-transformers (used lazily in app.py for embeddings) depends on torch.
# Installing CPU torch from PyTorch's wheel index first avoids huge default PyPI
# CUDA wheels and reduces ReadTimeoutError during `docker compose build`.
ENV PIP_DEFAULT_TIMEOUT=300

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies: upgrade pip, CPU torch, then the app stack.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 10 \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --retries 10 \
    fastapi \
    uvicorn[standard] \
    pydantic[dotenv] \
    requests \
    numpy \
    sentence-transformers \
    PyJWT \
    python-multipart

# Copy application code
COPY services/gateway/ ./
RUN test -f /app/app.py

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]
