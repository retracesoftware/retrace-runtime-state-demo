#!/usr/bin/env bash
set -euo pipefail

RECORDINGS_DIR=/app/recordings
REPORTS_DIR=/app/reports
STATE_DIR=/state
RECORDING=${RECORDINGS_DIR}/runtime-incident.retrace
REPORT_JSON=${RECORDINGS_DIR}/runtime-incident.ai-report.json
REPORT_MD=${RECORDINGS_DIR}/runtime-incident.ai-report.md
PAYLOAD=${STATE_DIR}/latest-payload.json
REQUEST_COUNT=${STATE_DIR}/request-count.txt

cd /app
python /app/scripts/wait_for_api.py

rm -rf "${RECORDINGS_DIR:?}/"*
rm -f \
    "${REPORTS_DIR}/runtime-incident.ai-report.md" \
    "${REPORTS_DIR}/runtime-incident.ai-report.json" \
    "${REPORTS_DIR}/runtime-incident.presentation.md" \
    "${REPORTS_DIR}/runtime-payload.json" \
    "${REPORTS_DIR}/demo-terminal.log" \
    "${REPORTS_DIR}/python-packages.log" \
    "${REPORTS_DIR}/replay-terminal.log"
rm -f "${PAYLOAD}" "${REQUEST_COUNT}"
mkdir -p "${RECORDINGS_DIR}" "${REPORTS_DIR}" "${STATE_DIR}"

python -m pip show retracesoftware | tee "${REPORTS_DIR}/python-packages.log"
python -m pip show retracesoftware-dap | tee -a "${REPORTS_DIR}/python-packages.log"
python --version | tee -a "${REPORTS_DIR}/python-packages.log"

export RETRACE_AUTO_DEBUG=1
export RETRACE_AI_TARGET=target_application
export RETRACE_AI_TASK="${RETRACE_AI_TASK:-Diagnose this pytest runtime failure from replay state. Inspect source and locals at the positioned failure line, then inspect the existing production helper calculate_revenue_per_retained_unit in /app/app/order_metrics.py before reporting. In the final report, quote the observed runtime_incident_evidence local verbatim, explain which values make the denominator zero, identify the revenue-per-retained-unit calculation, and recommend the narrow full-return handling rule in app/order_metrics.py. Cite only source paths you actually inspected. Do not invent files or substitute runtime values.}"

echo "Running the real pytest command through Retrace:"
echo "RETRACE_AUTO_DEBUG=1 retracepython --recording ${RECORDING} -m pytest -vs tests"

set +e
retracepython --recording "${RECORDING}" -m pytest -vs tests 2>&1 \
    | tee "${REPORTS_DIR}/demo-terminal.log"
status=${PIPESTATUS[0]}
set -e

if [[ "${status}" -ne 1 ]]; then
    echo "ERROR: expected pytest/Retrace exit code 1, got ${status}." >&2
    exit 1
fi

if [[ ! -s "${RECORDING}" || ! -s "${REPORT_MD}" || ! -s "${PAYLOAD}" ]]; then
    echo "ERROR: recording, AI report, or captured runtime payload is missing." >&2
    exit 1
fi

if [[ "$(cat "${REQUEST_COUNT}")" != "1" ]]; then
    echo "ERROR: expected one live API request across record and AI replay." >&2
    cat "${REQUEST_COUNT}" >&2
    exit 1
fi

cp "${REPORT_MD}" "${REPORTS_DIR}/runtime-incident.ai-report.md"
cp "${PAYLOAD}" "${REPORTS_DIR}/runtime-payload.json"
if [[ -s "${REPORT_JSON}" ]]; then
    cp "${REPORT_JSON}" "${REPORTS_DIR}/runtime-incident.ai-report.json"
else
    echo "ERROR: structured AI report is missing." >&2
    exit 1
fi

/app/scripts/replay_trace.sh "${RECORDING}"

python /app/scripts/render_presentation_report.py \
    "${REPORTS_DIR}/runtime-incident.ai-report.json" \
    "${REPORTS_DIR}/runtime-incident.presentation.md"

python /app/scripts/validate_report.py \
    "${REPORTS_DIR}/runtime-incident.presentation.md" \
    "${REPORTS_DIR}/runtime-payload.json" \
    "${REPORTS_DIR}/runtime-incident.ai-report.json"

echo ""
echo "Runtime-state demo succeeded."
echo "Recording: ${RECORDING}"
echo "Report:    ${REPORTS_DIR}/runtime-incident.presentation.md"
echo "Native:    ${REPORTS_DIR}/runtime-incident.ai-report.md"
echo "Payload:   ${REPORTS_DIR}/runtime-payload.json"
echo "Live API requests across record, AI replay, and direct replay: $(cat "${REQUEST_COUNT}")"
echo ""
sed -n '1,220p' "${REPORTS_DIR}/runtime-incident.presentation.md"
