#!/usr/bin/env bash
set -euo pipefail

report=${1:-reports/runtime-incident.presentation.md}

if [[ ! -s "${report}" ]]; then
    echo "Report is missing or empty: ${report}" >&2
    exit 1
fi

absolute_report="$(cd "$(dirname "${report}")" && pwd)/$(basename "${report}")"
echo "Report: ${absolute_report}"

if command -v open >/dev/null 2>&1; then
    open "${absolute_report}"
elif command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    xdg-open "${absolute_report}"
else
    sed -n '1,220p' "${absolute_report}"
fi
