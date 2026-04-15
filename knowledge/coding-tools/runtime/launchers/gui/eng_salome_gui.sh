#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GUI_ID="eng_salome_gui"
IMAGE="birtha/knowledge-eng-salome-gui:1.0.0"
PLATFORM="linux/amd64"
NOVNC_HOST_PORT="${NOVNC_HOST_PORT:-$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(('127.0.0.1', 0))
print(s.getsockname()[1])
s.close()
PY
)}"
NOVNC_PASSWORD="${NOVNC_PASSWORD:-$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)}"
ARTIFACT_DIR="${KNOWLEDGE_GUI_ARTIFACT_DIR:-$ROOT/.cache/knowledge-gui-artifacts/$GUI_ID}"
mkdir -p "$ARTIFACT_DIR"
echo "noVNC URL: http://127.0.0.1:${NOVNC_HOST_PORT}/vnc.html?autoconnect=true&resize=scale" >&2
echo "noVNC password: ${NOVNC_PASSWORD}" >&2
exec docker run --rm --platform "$PLATFORM" \
  -p "127.0.0.1:${NOVNC_HOST_PORT}:6080" \
  -e "NOVNC_PASSWORD=${NOVNC_PASSWORD}" \
  -e "KNOWLEDGE_GUI_SESSION_REF=artifact://gui-session-spec/eng_salome_gui" \
  -e "KNOWLEDGE_GUI_ARTIFACT_DIR=/artifacts" \
  -v "$ROOT:$ROOT" -w "$ROOT" \
  -v "$ARTIFACT_DIR:/artifacts" \
  "$IMAGE" "$@"
