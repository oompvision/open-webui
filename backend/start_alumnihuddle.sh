#!/usr/bin/env bash

# AlumniHuddle Start Script
# Uses our custom app wrapper that adds multi-tenancy support

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR" || exit

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

# Load secret key
if [ -n "${WEBUI_SECRET_KEY_FILE}" ]; then
    KEY_FILE="${WEBUI_SECRET_KEY_FILE}"
else
    KEY_FILE=".webui_secret_key"
fi

if test "$WEBUI_SECRET_KEY $WEBUI_JWT_SECRET_KEY" = " "; then
  echo "Loading WEBUI_SECRET_KEY from file, not provided as an environment variable."

  if ! [ -e "$KEY_FILE" ]; then
    echo "Generating WEBUI_SECRET_KEY"
    echo $(head -c 12 /dev/random | base64) > "$KEY_FILE"
  fi

  echo "Loading WEBUI_SECRET_KEY from $KEY_FILE"
  WEBUI_SECRET_KEY=$(cat "$KEY_FILE")
fi

PYTHON_CMD=$(command -v python3 || command -v python)
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

if [ "$#" -gt 0 ]; then
    ARGS=("$@")
else
    ARGS=(--workers "$UVICORN_WORKERS")
fi

echo "Starting AlumniHuddle (OpenWebUI + Multi-Tenancy)..."

# Use our custom app instead of open_webui.main:app
WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" exec "$PYTHON_CMD" -m uvicorn open_webui.alumnihuddle_app:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips '*' \
    "${ARGS[@]}"
