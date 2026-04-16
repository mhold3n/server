FROM python:3.11-slim-bookworm
WORKDIR /workspace
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine64 cabextract unzip && ln -s /usr/lib/wine/wine64 /usr/local/bin/wine64 && ln -s /usr/lib/wine/wineserver64 /usr/local/bin/wineserver64 && rm -rf /var/lib/apt/lists/*
RUN wine64 --version
CMD ["python"]
