FROM mambaorg/micromamba:1.5.10
USER root
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN micromamba install -y -n base -c conda-forge -c rmg python=3.9 rmg=3.3.0 && micromamba clean --all --yes
CMD ["bash"]
