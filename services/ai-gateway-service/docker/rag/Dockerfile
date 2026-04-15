FROM python:3.11-slim

WORKDIR /app

# sentence-transformers / transformers need torch. Default PyPI torch2.x pulls CUDA metapackages
# (nvidia-*, triton, …) — multi‑GB downloads that often hit ReadTimeoutError in Docker builds.
# Install CPU-only torch from PyTorch's wheel index first, then the rest (do not list `torch` again).
ENV PIP_DEFAULT_TIMEOUT=300

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 10 \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --retries 10 \
    fastapi \
    uvicorn[standard] \
    haystack-ai \
    qdrant-client \
    sentence-transformers \
    transformers \
    pydantic \
    requests \
    numpy \
    rank-bm25 \
    nltk \
    scikit-learn \
    python-multipart \
    huggingface_hub

# Copy application code
COPY services/rag/ ./

# Create cache directory
RUN mkdir -p /cache

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]