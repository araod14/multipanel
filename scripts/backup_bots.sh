#!/usr/bin/env bash
# Back up every per-user bot data directory (config + trades.sqlite + logs).
#
# Usage:
#   CP_BOT_DATA_ROOT=/srv/control-plane/bots ./backup_bots.sh [DEST_DIR]
#
# Produces one timestamped tar.gz per user under DEST_DIR (default: ./backups).
# Restore with:  tar -xzf <file> -C "$CP_BOT_DATA_ROOT"
set -euo pipefail

ROOT="${CP_BOT_DATA_ROOT:-/srv/control-plane/bots}"
DEST="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! -d "$ROOT" ]]; then
  echo "bot data root not found: $ROOT" >&2
  exit 1
fi

mkdir -p "$DEST"

shopt -s nullglob
for userdir in "$ROOT"/*/; do
  user="$(basename "$userdir")"
  out="$DEST/${user}-${STAMP}.tar.gz"
  tar -czf "$out" -C "$ROOT" "$user"
  echo "backed up $user -> $out"
done

echo "done. backups in $DEST"
