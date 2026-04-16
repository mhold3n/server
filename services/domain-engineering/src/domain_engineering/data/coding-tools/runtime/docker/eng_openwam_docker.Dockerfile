FROM debian:bookworm-slim
SHELL ["bash", "-lc"]
WORKDIR /workspace
RUN dpkg --add-architecture i386 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git cmake make g++ mingw-w64 wine64 xvfb xauth ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/CMT-UPV/OpenWAM.git /tmp/OpenWAM && sed -i 's/<Windows.h>/<windows.h>/' /tmp/OpenWAM/Source/TOpenWAM.cpp && cd /tmp/OpenWAM && cmake -B build -S . -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++ -DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres && cmake --build build -j2
RUN exe=$(find /tmp/OpenWAM/build -iname 'OpenWAM*.exe' -print -quit) && test -n "$exe" && install -d /opt/openwam/probe && install -m755 "$exe" /opt/openwam/OpenWAM.exe && cp $(find /usr/lib/gcc/x86_64-w64-mingw32 -name 'libgcc_s_seh-1.dll' -print -quit) /opt/openwam/ && cp $(find /usr/lib/gcc/x86_64-w64-mingw32 -name 'libstdc++-6.dll' -print -quit) /opt/openwam/ && cp /usr/x86_64-w64-mingw32/lib/libwinpthread-1.dll /opt/openwam/ && : > /opt/openwam/probe/missing.wam
CMD ["bash"]
