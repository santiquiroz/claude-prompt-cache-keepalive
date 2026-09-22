#!/usr/bin/env bash
set -euo pipefail

MINUTES="${1:?usage: rung.sh <minutes> [label] [state-dir]}"
LABEL="${2:-tick}"
STATE_DIR="${3:-$HOME/.claude/keepalive/default}"
POLL_SECONDS=60
STOP_FILE="$STATE_DIR/stop"
mkdir -p "$STATE_DIR"

deadline=$(( $(date +%s) + $(awk "BEGIN{print int($MINUTES*60)}") ))

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i -w $$ &
elif command -v systemd-inhibit >/dev/null 2>&1; then
  systemd-inhibit --what=idle:sleep --why="keeping prompt cache warm" --mode=block \
    sleep $(( deadline - $(date +%s) + 60 )) >/dev/null 2>&1 &
fi

while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$STOP_FILE" ]; then echo "KEEPALIVE_STOPPED $LABEL"; exit 0; fi
  left=$(( deadline - $(date +%s) ))
  sleep $(( left < POLL_SECONDS ? (left > 0 ? left : 1) : POLL_SECONDS ))
done
if [ -f "$STOP_FILE" ]; then echo "KEEPALIVE_STOPPED $LABEL"; exit 0; fi
echo "KEEPALIVE_TICK $LABEL $(date +%Y-%m-%dT%H:%M:%S) - reply with one short line, no tools"
