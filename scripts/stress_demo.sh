#!/usr/bin/env bash
set -euo pipefail

runs=${1:-5}
archive=/app/reports/stress
scratch=/tmp/retrace-runtime-demo-stress

rm -rf "${archive}" "${scratch}"
mkdir -p "${archive}" "${scratch}"
failures=0

save_results() {
    mkdir -p "${archive}"
    cp -R "${scratch}/." "${archive}/"
}

trap save_results EXIT

for run in $(seq 1 "${runs}"); do
    label="run-$(printf '%02d' "${run}")"
    echo ""
    echo "===== ${label}/${runs} ====="
    set +e
    /app/scripts/run_demo.sh
    status=$?
    set -e

    mkdir -p "${scratch}/${label}"
    printf '%s\n' "${status}" > "${scratch}/${label}/exit-status.txt"
    for artifact in \
        runtime-incident.ai-report.md \
        runtime-incident.presentation.md \
        runtime-payload.json \
        demo-terminal.log \
        replay-terminal.log; do
        if [[ -f "/app/reports/${artifact}" ]]; then
            cp "/app/reports/${artifact}" "${scratch}/${label}/"
        fi
    done
    if [[ -s /app/reports/runtime-incident.ai-report.json ]]; then
        cp /app/reports/runtime-incident.ai-report.json "${scratch}/${label}/"
    fi
    if [[ "${status}" -ne 0 ]]; then
        failures=$((failures + 1))
    fi
done

save_results
echo "Saved ${runs} validated runs under ${archive}."

if [[ "${failures}" -ne 0 ]]; then
    echo "${failures}/${runs} run(s) failed the end-to-end quality gate." >&2
    exit 1
fi
