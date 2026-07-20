#!/usr/bin/env bash
set -euo pipefail

RECORDING=${1:-/app/recordings/runtime-incident.retrace}
REPORTS_DIR=/app/reports
REQUEST_COUNT_PATH=/state/request-count.txt

if [[ ! -s "${RECORDING}" ]]; then
    echo "recording missing: ${RECORDING}" >&2
    exit 1
fi

before_count="$(cat "${REQUEST_COUNT_PATH}")"
retrace-dap --recording "${RECORDING}" --extract

TRACE_DIR="${RECORDING%.retrace}.d"
pidfile="$(find "${TRACE_DIR}" -name '*.bin' -type f | sort | head -n 1)"
if [[ -z "${pidfile}" ]]; then
    echo "no extracted pidfile found under ${TRACE_DIR}" >&2
    exit 1
fi

echo "Replaying ${pidfile}"
set +e
"${pidfile}" 2>&1 | tee "${REPORTS_DIR}/replay-terminal.log"
status=${PIPESTATUS[0]}
set -e

if [[ "${status}" -ne 1 ]]; then
    echo "ERROR: expected replay to preserve pytest exit code 1, got ${status}." >&2
    exit 1
fi

after_count="$(cat "${REQUEST_COUNT_PATH}")"
if [[ "${before_count}" != "${after_count}" ]]; then
    echo "ERROR: replay contacted the live incident API." >&2
    echo "request count changed from ${before_count} to ${after_count}" >&2
    exit 1
fi

echo "Replay reproduced the runtime failure without another API request."
