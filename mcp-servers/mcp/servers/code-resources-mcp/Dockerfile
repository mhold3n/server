FROM python:3.10-slim-buster

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml poetry.lock* ./
RUN pip install poetry && poetry install --no-root --no-dev

# Copy source code
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data

EXPOSE 7002

CMD ["poetry", "run", "python", "src/server.py"]











