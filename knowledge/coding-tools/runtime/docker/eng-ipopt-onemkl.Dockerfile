FROM ubuntu:24.04
SHELL ["/bin/bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates wget gpg build-essential cmake ninja-build pkg-config git gfortran python3 python3-pip coinor-libipopt-dev && rm -rf /var/lib/apt/lists/*
RUN wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor > /usr/share/keyrings/oneapi-archive-keyring.gpg && echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" > /etc/apt/sources.list.d/oneAPI.list && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends intel-oneapi-mkl intel-oneapi-mkl-devel && rm -rf /var/lib/apt/lists/*
COPY HSL/coinhsl-2024.05.15 /opt/vendor/coinhsl-src
COPY HSL/CoinHSL.v2024.5.15.aarch64-apple-darwin-libgfortran5 /opt/vendor/coinhsl-prebuilt-darwin
RUN test -f /opt/vendor/coinhsl-src/README && test -d /opt/vendor/coinhsl-src/ma57 && test -d /opt/vendor/coinhsl-src/hsl_ma77 && test -d /opt/vendor/coinhsl-src/hsl_ma86 && test -d /opt/vendor/coinhsl-src/hsl_ma97
RUN test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so
CMD ["bash"]
