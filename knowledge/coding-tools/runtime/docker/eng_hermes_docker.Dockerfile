FROM ubuntu:24.04
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake ninja-build build-essential gfortran freeglut3-dev libsuitesparse-dev libglew-dev libxerces-c-dev xsdcxx libmatio-dev python3 ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/hpfem/hermes.git /tmp/hermes && cd /tmp/hermes && cp CMake.vars.example.Linux CMake.vars && python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/hermes/CMake.vars')
text=p.read_text()
for old,new in [('set(H2D_WITH_GLUT YES)','set(H2D_WITH_GLUT NO)'),('set(H2D_WITH_TEST_EXAMPLES YES)','set(H2D_WITH_TEST_EXAMPLES NO)')]:
    text=text.replace(old,new)
p.write_text(text)
PY
RUN cd /tmp/hermes && cmake -B build -S . -GNinja -DCMAKE_INSTALL_PREFIX=/opt/hermes && cp build/hermes_common/include/config.h hermes_common/include/config.h && cp build/hermes2d/include/config.h hermes2d/include/config.h && ln -snf /tmp/hermes/hermes2d/xml_schemas build/hermes2d/xml_schemas && rm -rf build/hermes2d/include && ln -snf /tmp/hermes/hermes2d/include build/hermes2d/include && rm -rf build/hermes2d/src && ln -snf /tmp/hermes/hermes2d/src build/hermes2d/src && cmake --build build -j2 && cmake --install build
RUN printf '%s\n' '#!/bin/sh' 'test -f /opt/hermes/include/hermes2d/hermes2d.h' 'test -f /opt/hermes/include/hermes_common/hermes_common.h' 'find /opt/hermes -name "libhermes2d*.so*" -o -name "libhermes_common*.so*" | grep -q .' 'echo OK:hermes' >/usr/local/bin/hermes_probe && chmod +x /usr/local/bin/hermes_probe
CMD ["bash"]
