#!/usr/bin/env bash
set -euo pipefail
export DISPLAY="${DISPLAY:-:99}"
export SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1440x900x24}"
export KNOWLEDGE_GUI_ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-/artifacts}"
mkdir -p "$KNOWLEDGE_GUI_ARTIFACT_DIR"
if ! pgrep -f "Xvfb.*${DISPLAY}" >/dev/null 2>&1; then
  Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp >/tmp/knowledge-gui-health-xvfb.log 2>&1 &
  sleep 1
fi
xdpyinfo >/tmp/knowledge-gui-xdpyinfo.log
glxinfo -B >/tmp/knowledge-gui-glxinfo.log 2>&1 || true
scrot "$KNOWLEDGE_GUI_ARTIFACT_DIR/gui-healthcheck.png"
test -s "$KNOWLEDGE_GUI_ARTIFACT_DIR/gui-healthcheck.png"
echo OK:container-gui-healthcheck
