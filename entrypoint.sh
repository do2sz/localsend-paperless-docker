#!/usr/bin/env bash
# Supervisor: starts localsend-cli (receiver) and the Paperless forwarder.
# Exits with non-zero status as soon as one of the two processes dies, so
# Docker restart-policy can bring the container back up.
# Requires bash (uses `wait -n`); python:3.13-slim ships bash by default.

set -eu

INCOMING_DIR="${INCOMING_DIR:-/data/incoming}"
ALIAS="${LOCALSEND_ALIAS:-Paperless Inbox}"

mkdir -p "$INCOMING_DIR" "${RETRY_DIR:-/data/retry}"

# Build optional PIN flag
set -- recv -d "$INCOMING_DIR" -n "$ALIAS"
if [ -n "${LOCALSEND_PIN:-}" ]; then
    set -- "$@" -p "$LOCALSEND_PIN"
fi

echo "[entrypoint] starting localsend-cli $*"
localsend-cli "$@" &
LS_PID=$!

echo "[entrypoint] starting forwarder"
python -m forwarder &
FW_PID=$!

term() {
    echo "[entrypoint] received termination signal, shutting down"
    kill -TERM "$LS_PID" "$FW_PID" 2>/dev/null || true
}
trap term TERM INT

# Exit as soon as either child exits
wait -n "$LS_PID" "$FW_PID"
EXIT_CODE=$?
echo "[entrypoint] a child process exited with $EXIT_CODE, stopping the other"
kill -TERM "$LS_PID" "$FW_PID" 2>/dev/null || true
wait || true
exit "$EXIT_CODE"
