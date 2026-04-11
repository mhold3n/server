FROM mambaorg/micromamba:1.5.10
USER root
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN micromamba install -y -n base -c conda-forge python=3.11 petsc petsc4py slepc slepc4py hypre mpi4py && micromamba clean --all --yes
ENV PATH="/opt/conda/bin:${PATH}"
RUN ln -sf /opt/conda/bin/python /usr/local/bin/python || true
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir primme
CMD ["bash"]
