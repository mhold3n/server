FROM python:3.11-slim
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN python3 -m pip install --break-system-packages --no-cache-dir pychrono
CMD ["bash"]