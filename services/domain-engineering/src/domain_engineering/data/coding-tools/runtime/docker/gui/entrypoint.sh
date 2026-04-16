#!/usr/bin/env bash
set -euo pipefail
export DISPLAY="${DISPLAY:-:99}"
export VNC_PORT="${VNC_PORT:-5900}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"
export SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1440x900x24}"
export KNOWLEDGE_GUI_ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-/artifacts}"
if [ -z "${NOVNC_PASSWORD:-}" ]; then
  echo "NOVNC_PASSWORD is required for container GUI sessions" >&2
  exit 64
fi
mkdir -p "$KNOWLEDGE_GUI_ARTIFACT_DIR" /tmp/knowledge-gui
Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" -nolisten tcp >/tmp/knowledge-gui/xvfb.log 2>&1 &
sleep 1
fluxbox >/tmp/knowledge-gui/fluxbox.log 2>&1 &
x11vnc -display "$DISPLAY" -localhost -forever -shared -rfbport "$VNC_PORT" -passwd "$NOVNC_PASSWORD" >/tmp/knowledge-gui/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ --heartbeat=30 0.0.0.0:"$NOVNC_PORT" 127.0.0.1:"$VNC_PORT" >/tmp/knowledge-gui/novnc.log 2>&1 &
sleep 1
if [ "$#" -eq 0 ]; then
  set -- xterm
fi
"$@" &
app_pid=$!
wait "$app_pid"
