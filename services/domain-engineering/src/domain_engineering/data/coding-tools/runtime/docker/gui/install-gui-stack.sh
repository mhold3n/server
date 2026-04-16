#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl fonts-dejavu-core fonts-liberation fluxbox imagemagick \
  mesa-utils novnc procps python3 scrot websockify x11-utils x11vnc \
  xdotool xterm xvfb
if ! command -v tini >/dev/null 2>&1; then
  if ! apt-get install -y --no-install-recommends tini; then
    curl -fsSL https://github.com/krallin/tini/releases/download/v0.19.0/tini-amd64 \
      -o /usr/local/bin/tini
    chmod +x /usr/local/bin/tini
  fi
fi
rm -rf /var/lib/apt/lists/*
