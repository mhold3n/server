FROM python:3.11-slim

WORKDIR /app

# Build context is services/wrkhrs/, so the live gateway source is under
# services/gateway/ within that subtree.

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
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
