FROM intel/oneapi-basekit:latest
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash ca-certificates python3 python3-pip pkg-config git wget gpg build-essential cmake ninja-build gfortran coinor-libipopt-dev && rm -rf /var/lib/apt/lists/*
COPY HSL/coinhsl-2024.05.15 /opt/vendor/coinhsl-src
COPY HSL/CoinHSL.v2024.5.15.aarch64-apple-darwin-libgfortran5 /opt/vendor/coinhsl-prebuilt-darwin
RUN test -f /opt/vendor/coinhsl-src/README && test -d /opt/vendor/coinhsl-src/ma57 && test -d /opt/vendor/coinhsl-src/hsl_ma77 && test -d /opt/vendor/coinhsl-src/hsl_ma86 && test -d /opt/vendor/coinhsl-src/hsl_ma97
RUN test -f /opt/intel/oneapi/mkl/latest/lib/libmkl_rt.so
RUN ln -sf /usr/bin/python3 /usr/local/bin/python || true
CMD ["bash"]
