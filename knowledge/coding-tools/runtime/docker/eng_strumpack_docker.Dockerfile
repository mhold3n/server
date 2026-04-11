FROM ubuntu:24.04
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build build-essential gfortran libopenmpi-dev openmpi-bin libopenblas-dev liblapack-dev libscalapack-openmpi-dev libmetis-dev ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/pghysels/STRUMPACK.git /tmp/STRUMPACK && mkdir -p /tmp/build-strumpack && cd /tmp/build-strumpack && cmake -G Ninja -DCMAKE_INSTALL_PREFIX=/opt/strumpack -DSTRUMPACK_USE_MPI=OFF -DSTRUMPACK_USE_OPENMP=ON -DTPL_ENABLE_SCOTCH=OFF -DTPL_ENABLE_PTSCOTCH=OFF -DTPL_ENABLE_PARMETIS=OFF -DTPL_ENABLE_BPACK=OFF -DTPL_ENABLE_ZFP=OFF -DTPL_ENABLE_SLATE=OFF -DTPL_ENABLE_COMBBLAS=OFF /tmp/STRUMPACK && ninja install
RUN printf '%s\n' '#include <StrumpackSparseSolver.hpp>' 'int main(){return 0;}' >/tmp/strumpack_probe.cpp && g++ -I/opt/strumpack/include /tmp/strumpack_probe.cpp -o /usr/local/bin/strumpack_probe
CMD ["bash"]
