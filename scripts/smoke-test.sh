#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost/api/v1/openapi.json}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost/}"
MAX_WAIT="${MAX_WAIT:-120}"
INTERVAL=3

echo "Smoke test: waiting up to ${MAX_WAIT}s for stack to become healthy..."

wait_for() {
    local url="$1"
    local label="$2"
    local elapsed=0
    until curl -sf --max-time 5 "$url" > /dev/null 2>&1; do
        if [ "$elapsed" -ge "$MAX_WAIT" ]; then
            echo "FAIL: $label did not respond at $url within ${MAX_WAIT}s"
            exit 1
        fi
        sleep "$INTERVAL"
        elapsed=$((elapsed + INTERVAL))
        echo "  waiting for $label... (${elapsed}s)"
    done
    echo "OK: $label responded at $url"
}

wait_for "$BACKEND_URL" "backend"
wait_for "$FRONTEND_URL" "frontend"

echo "Smoke test passed."
