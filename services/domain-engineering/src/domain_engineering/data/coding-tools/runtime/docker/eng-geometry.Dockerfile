FROM python:3.11-slim
WORKDIR /workspace
COPY knowledge/coding-tools/runtime/uv/eng-geometry.requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /tmp/requirements.txt
ENTRYPOINT ["python"]
