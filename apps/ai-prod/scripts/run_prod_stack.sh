#!/usr/bin/env bash
set -euo pipefail

BACKEND_HOST="${AI_PROD_PY_BACKEND_BIND_HOST:-127.0.0.1}"
BACKEND_PORT="${AI_PROD_PY_BACKEND_PORT:-26014}"
CPP_BINARY="${AI_PROD_CPP_BINARY_PATH:-/workspace/cpp/ai_prod_cpp_proxy}"

export AI_PROD_PY_BACKEND_HOST="${AI_PROD_PY_BACKEND_HOST:-127.0.0.1}"
export AI_PROD_PY_BACKEND_PORT="${BACKEND_PORT}"
export AI_PROD_CPP_BIND_HOST="${AI_PROD_CPP_BIND_HOST:-0.0.0.0}"
export AI_PROD_CPP_BIND_PORT="${AI_PROD_CPP_BIND_PORT:-26004}"

python3 -m uvicorn app.main:app \
  --app-dir /workspace/backend \
  --host "${BACKEND_HOST}" \
  --port "${BACKEND_PORT}" &
BACKEND_PID=$!

cleanup() {
  if kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

BACKEND_HOST="${BACKEND_HOST}" BACKEND_PORT="${BACKEND_PORT}" python3 - <<'PY'
import os
import time
import urllib.error
import urllib.request

host = os.environ["BACKEND_HOST"]
port = os.environ["BACKEND_PORT"]
url = f"http://{host}:{port}/api/v1/health"

last_error = ""
for _ in range(120):
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            if response.status == 200:
                raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
        time.sleep(0.5)

raise SystemExit(f"ai-prod backend failed to become ready: {last_error}")
PY

"${CPP_BINARY}" &
CPP_PID=$!

set +e
wait -n "${BACKEND_PID}" "${CPP_PID}"
STATUS=$?
set -e

if kill -0 "${CPP_PID}" >/dev/null 2>&1; then
  kill "${CPP_PID}" >/dev/null 2>&1 || true
  wait "${CPP_PID}" >/dev/null 2>&1 || true
fi

exit "${STATUS}"
