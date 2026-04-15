FROM python:3.11-slim

WORKDIR /app

# Large PyPI wheels (torch) are not used: services/asr uses faster-whisper → CTranslate2 only.
# Keeping the install set small avoids multi‑GB downloads that often hit ReadTimeoutError on PyPI.
ENV PIP_DEFAULT_TIMEOUT=300

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (upgrade pip first for better resume on slow links)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 10 \
    fastapi \
    uvicorn[standard] \
    faster-whisper \
    pydantic \
    requests \
    numpy \
    python-multipart \
    huggingface_hub

# Copy application code
COPY services/asr/ ./

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]