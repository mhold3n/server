FROM ubuntu:24.04
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash ca-certificates calculix-ccx && rm -rf /var/lib/apt/lists/*
CMD ["bash"]
