FROM python:3.11-slim
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash ca-certificates libgomp1 && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --break-system-packages --no-cache-dir KratosMultiphysics
CMD ["bash"]