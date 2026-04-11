FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY services/model-runtime ./services/model-runtime
COPY services/engineering-core ./services/engineering-core
COPY schemas ./schemas

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e ./services/engineering-core -e "./services/model-runtime[hf]"

ENV MODEL_RUNTIME_HOST=0.0.0.0
ENV MODEL_RUNTIME_PORT=8000
ENV MODEL_RUNTIME_CONFIG_PATH=/app/services/model-runtime/config/models.yaml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "model_runtime.main"]
