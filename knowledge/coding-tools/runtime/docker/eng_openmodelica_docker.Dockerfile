FROM openmodelica/openmodelica:v1.26.3-minimal
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash ca-certificates python3 python3-pip && rm -rf /var/lib/apt/lists/*
CMD ["bash"]
