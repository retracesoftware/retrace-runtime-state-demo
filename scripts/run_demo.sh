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
CORRECTION_ATTEMPTS=${RETRACE_AI_CORRECTION_ATTEMPTS:-1}

if [[ "${CORRECTION_ATTEMPTS}" != "0" && "${CORRECTION_ATTEMPTS}" != "1" ]]; then
    echo "ERROR: RETRACE_AI_CORRECTION_ATTEMPTS must be 0 or 1." >&2
    exit 2
fi

cd /app
python /app/scripts/wait_for_api.py

rm -rf "${RECORDINGS_DIR:?}/"*
rm -f \
    "${REPORTS_DIR}/runtime-incident.ai-report.md" \
    "${REPORTS_DIR}/runtime-incident.ai-report.json" \
    "${REPORTS_DIR}/runtime-bug-report.md" \
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
export RETRACE_AI_TASK="${RETRACE_AI_TASK:-Diagnose this pytest runtime failure from replay state. Inspect source and locals at the positioned failure line, then inspect the existing production helper calculate_revenue_per_retained_unit at /app/app/order_metrics.py line 25 before reporting. In the final report, quote the observed runtime_incident_evidence local verbatim and show shipped_units - returned_units = retained_units using the observed numbers. When shipped_units equals returned_units, retained_units=0 is correctly computed for a fully returned order; the defect is the unguarded undefined division, not missing or incorrectly computed data. Recommend an explicit full-return policy in app/order_metrics.py: skip the metric or represent it as not applicable/None before division. Do not recommend silently returning numeric zero unless an application business rule explicitly defines that meaning. Cite only source paths and values actually returned by tools. Do not invent files or substitute runtime values.}"
RETRACE_AI_CORRECTION_TASK="${RETRACE_AI_CORRECTION_TASK:-A prior summary of this trace failed evidence validation. Re-investigate the pytest failure from replay state and produce a corrected evidence-specific report. Stop at /app/tests/test_order_metrics.py line 31. Read Locals and quote runtime_incident_evidence verbatim in report.evidence[].observed. Treat every numeric local as present data: do not claim revenue data is missing. Critical semantic rule: when shipped_units equals returned_units, retained_units = shipped_units - returned_units = 0 is correctly computed for a fully returned order. Do not call retained_units incorrect, missing, or incorrectly set. The defect is performing an undefined per-retained-unit division without handling that valid full-return state. Inspect calculate_revenue_per_retained_unit at /app/app/order_metrics.py line 25 before proposing a change. Recommend an explicit policy for fully returned orders: skip this undefined metric or represent it as not applicable/None before division. Do not silently map it to numeric zero without a business rule. Cite only source locations and values actually returned by tools.}"

cat <<'EOF'

EXPECTED DEMO BEHAVIOR
----------------------
Pytest will print FAILED and ZeroDivisionError below. That failure is
intentional: it is the runtime incident Retrace is recording. Do not stop the
command when it appears. After pytest exits, Retrace will replay the trace,
inspect the preserved runtime state through DAP, generate a bug report, and
verify that replay did not call the live API again.
EOF

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

render_and_validate() {
    python /app/scripts/render_bug_report.py \
        "${REPORTS_DIR}/runtime-incident.ai-report.json" \
        "${REPORTS_DIR}/runtime-bug-report.md" \
        && python /app/scripts/validate_report.py \
            "${REPORTS_DIR}/runtime-bug-report.md" \
            "${REPORTS_DIR}/runtime-payload.json" \
            "${REPORTS_DIR}/runtime-incident.ai-report.json"
}

if ! render_and_validate; then
    if [[ "${CORRECTION_ATTEMPTS}" == "0" ]]; then
        echo "Initial AI report failed validation; correction is disabled for this run." >&2
        exit 1
    fi
    echo "Initial AI summary did not meet the runtime-evidence quality gate."
    echo "Re-investigating the same recording once; pytest and the live API are not rerun."
    INITIAL_REPORT=/tmp/runtime-incident.initial-ai-report.json
    CORRECTED_REPORT=/tmp/runtime-incident.corrected-ai-report.json
    cp "${REPORT_JSON}" "${INITIAL_REPORT}"
    VERIFIED_RUNTIME_EVIDENCE="$(
        python /app/scripts/extract_verified_runtime_evidence.py \
            "${INITIAL_REPORT}" \
            "${REPORTS_DIR}/runtime-payload.json"
    )"
    retrace-ai-driver \
        --trace "${RECORDING}" \
        --target target_application \
        --report-out "${CORRECTED_REPORT}" \
        --report-md "${REPORT_MD}" \
        --task "${RETRACE_AI_CORRECTION_TASK} The quality gate verified this exact runtime_incident_evidence in the prior DAP transcript: '${VERIFIED_RUNTIME_EVIDENCE}'. Re-read and preserve it verbatim; changing any identifier or number is invalid." \
        --max-tool-calls "${RETRACE_AI_MAX_TOOL_CALLS:-70}" \
        --time-budget "${RETRACE_AI_TIME_BUDGET:-240}" \
        --max-output-tokens "${RETRACE_AI_MAX_OUTPUT_TOKENS:-8192}"
    python /app/scripts/merge_ai_correction.py \
        "${INITIAL_REPORT}" \
        "${CORRECTED_REPORT}" \
        "${REPORT_JSON}"
    cp "${REPORT_MD}" "${REPORTS_DIR}/runtime-incident.ai-report.md"
    cp "${REPORT_JSON}" "${REPORTS_DIR}/runtime-incident.ai-report.json"
    render_and_validate
fi

if [[ "$(cat "${REQUEST_COUNT}")" != "1" ]]; then
    echo "ERROR: AI correction replay contacted the live incident API." >&2
    exit 1
fi

echo ""
echo "Runtime-state demo succeeded."
echo "Recording: ${RECORDING}"
echo "Bug report: ${REPORTS_DIR}/runtime-bug-report.md"
echo "Native:    ${REPORTS_DIR}/runtime-incident.ai-report.md"
echo "Payload:   ${REPORTS_DIR}/runtime-payload.json"
echo "Live API requests across record, AI replay, and direct replay: $(cat "${REQUEST_COUNT}")"
echo ""
sed -n '1,220p' "${REPORTS_DIR}/runtime-bug-report.md"
