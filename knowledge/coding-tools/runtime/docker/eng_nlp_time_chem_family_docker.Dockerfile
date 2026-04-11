FROM mambaorg/micromamba:1.5.10
USER root
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN micromamba install -y -n base -c conda-forge python=3.11 sundials && micromamba clean --all --yes
ENV PATH="/opt/conda/bin:${PATH}"
RUN ln -sf /opt/conda/bin/python /usr/local/bin/python || true
CMD ["bash"]
