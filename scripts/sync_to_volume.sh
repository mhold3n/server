#!/usr/bin/env bash
#
# Reliable, headless directory (or file) sync to a second path — typically a removable
# volume. Uses rsync with resume-friendly flags; avoids Finder’s fragile large copies
# and does not copy iCloud placeholders as “real” data (source must be local first).
#
# Other agents: callers must ensure SOURCE is fully downloaded (not 0-byte cloud stubs).
# If unsure, run `du -sh SOURCE` and spot-check large files before syncing.
#
# Usage:
#   ./scripts/sync_to_volume.sh <source> <destination>
#   DRY_RUN=1 ./scripts/sync_to_volume.sh <source> <destination>
#
# Examples (from repo root, after chmod +x):
#   ./scripts/sync_to_volume.sh ~/GitHub/server /Volumes/ESD-USB/server
#   ./scripts/sync_to_volume.sh /path/to/calculix_replay_full_v4 /Volumes/ESD-USB/calculix_replay_full_v4
#

set -euo pipefail

SOURCE="${1:-}"
DEST="${2:-}"

if [[ -z "$SOURCE" || -z "$DEST" ]]; then
  echo "Usage: $0 <source> <destination>" >&2
  echo "  DRY_RUN=1 $0 <source> <destination>  # list actions only" >&2
  exit 1
fi

if [[ ! -e "$SOURCE" ]]; then
  echo "ERROR: source does not exist: $SOURCE" >&2
  exit 1
fi

# Resolve SOURCE to an absolute path
if [[ -d "$SOURCE" ]]; then
  SOURCE="$(cd "$SOURCE" && pwd)"
else
  SOURCE="$(cd "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
fi

mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"

echo "[sync_to_volume] SOURCE=$SOURCE"
echo "[sync_to_volume] DEST=$DEST"

if ! touch "$DEST/.sync_to_volume_write_test" 2>/dev/null; then
  echo "ERROR: destination is not writable: $DEST" >&2
  exit 1
fi
rm -f "$DEST/.sync_to_volume_write_test"

RSYNC=(rsync)
# macOS ships an older rsync; these flags are widely supported:
#   -a  archive (perms, times, recurse for dirs)
#   -h  human sizes
#   --partial        keep partially transferred files for resume
#   --progress       per-file progress
#   --stats          summary at end
RSYNC+=( -ah --partial --progress --stats )

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  RSYNC+=( --dry-run )
  echo "[sync_to_volume] DRY_RUN=1 (no files written)"
fi

# Optional: omit metadata that can confuse cross-volume copies (uncomment if needed)
# RSYNC+=( --no-perms --no-owner --no-group )

echo "[sync_to_volume] starting rsync..."
if [[ -d "$SOURCE" ]]; then
  # Trailing slashes: copy directory *contents* semantics — here we mirror tree into DEST
  "${RSYNC[@]}" "$SOURCE/" "$DEST/"
else
  "${RSYNC[@]}" "$SOURCE" "$DEST"
fi

echo "[sync_to_volume] done."
echo "[sync_to_volume] verify with: du -sh \"$SOURCE\" \"$DEST\""
