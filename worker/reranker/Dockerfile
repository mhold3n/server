FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.* \
    uvicorn[standard]==0.34.* \
    sentence-transformers==3.* \
    torch --index-url https://download.pytorch.org/whl/cu121

COPY app.py .

CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]
