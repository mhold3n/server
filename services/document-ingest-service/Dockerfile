FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    inotify-tools curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt && \
    (pip install marker-pdf || true)

COPY src /app/src

ENV INPUT_DIR=/documents OUTPUT_DIR=/processed LOG_LEVEL=INFO ERROR_WEBHOOK_URL=

CMD ["python", "-m", "src.main"]

