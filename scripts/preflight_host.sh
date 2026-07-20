#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed or not on PATH." >&2
    exit 2
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running." >&2
    exit 2
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose is not available through 'docker compose'." >&2
    exit 2
fi

if [[ -n "${RETRACE_API_KEY:-}" ]]; then
    ai_mode="configured Retrace API key"
else
    ai_mode="anonymous hosted allowance"
fi

echo "Preflight passed: $(uname -s)/$(uname -m), AI mode: ${ai_mode}."
