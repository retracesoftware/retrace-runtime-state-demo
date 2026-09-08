from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _text(value: Any, fallback: str = "Not provided.") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _references(values: list[Any] | None) -> str:
    return ", ".join(str(value) for value in values or [] if value not in (None, ""))


def _coordinate(coordinate: dict[str, Any]) -> str:
    parts: list[str] = []
    path = coordinate.get("path")
    line = coordinate.get("line")
    if path:
        parts.append(f"{path}:{line}" if line not in (None, 0) else str(path))
    function = coordinate.get("function")
    if function:
        parts.append(f"function {function}")
    thread_id = coordinate.get("thread_id")
    if thread_id is not None:
        parts.append(f"thread {thread_id}")
    message_index = coordinate.get("message_index")
    if message_index is not None:
        parts.append(f"message {message_index}")
    cursor = coordinate.get("cursor")
    if cursor:
        parts.append(f"cursor {_text(cursor)}")
    return ", ".join(parts) or "No durable replay coordinate was reported."


def _location(location: dict[str, Any]) -> str:
    path = _text(location.get("path"), "unknown path")
    line = location.get("line")
    frame = location.get("frame")
    parts = [path]
    if line is not None:
        parts.append(f"line {line}")
    if frame is not None:
        parts.append(f"frame {frame}")
    return ", ".join(parts)


def _evidence_location(item: dict[str, Any]) -> str:
    coordinate = item.get("coordinate")
    if isinstance(coordinate, dict):
        return _coordinate(coordinate)
    return _location(item.get("location") or {})


def _verified_runtime_evidence(payload: dict[str, Any]) -> str | None:
    for entry in reversed(payload.get("transcript") or []):
        if entry.get("tool") != "get_variables":
            continue
        variables = (
            ((entry.get("result") or {}).get("data") or {}).get("variables") or []
        )
        for variable in variables:
            if variable.get("name") == "runtime_incident_evidence":
                value = str(variable.get("value", "")).strip("'\"")
                if value:
                    return value
    return None


def _append_claim(
    lines: list[str],
    heading: str,
    claim: dict[str, Any] | None,
) -> None:
    if not claim or not claim.get("claim"):
        return
    lines.extend([f"## {heading}", "", _text(claim.get("claim")), ""])
    evidence_ids = _references(claim.get("evidence_ids"))
    if evidence_ids:
        lines.extend([f"Evidence: `{evidence_ids}`", ""])


def _append_string_list(
    lines: list[str],
    heading: str,
    values: list[Any] | None,
    *,
    show_empty: bool = False,
) -> None:
    if not values and not show_empty:
        return
    lines.extend([f"## {heading}", ""])
    if values:
        lines.extend(f"- {_text(value)}" for value in values)
    else:
        lines.append("- None reported.")
    lines.append("")


def _append_observed(lines: list[str], observed: Any) -> None:
    text = _text(observed)
    lines.extend(["Observed:", ""])
    lines.extend(f"    {line}" for line in text.splitlines() or [text])
    lines.append("")


def normalize_document(document: dict[str, Any]) -> dict[str, Any]:
    if isinstance(document.get("report"), dict):
        return document
    if "status" in document and "title" in document:
        return {"report": document, "transcript": []}
    raise ValueError("structured AI report is missing report object")


def render(payload: dict[str, Any]) -> str:
    report = payload["report"]
    root_cause = report.get("root_cause") or {}
    reproducibility = report.get("reproducibility") or {}
    suggested_fix = report.get("suggested_fix") or {}
    lines = [
        f"# {_text(report.get('title'), 'Retrace AI Debug Report')}",
        "",
        "> Bug report rendered from structured Retrace AI findings. "
        "No diagnostic claims have been added or rewritten.",
        "",
        "## Summary",
        "",
        _text(report.get("summary")),
        "",
    ]

    verified_runtime_evidence = _verified_runtime_evidence(payload)
    if verified_runtime_evidence:
        lines.extend(
            [
                "## Verified DAP Runtime State",
                "",
                "The debugger read this value directly from the historical Locals scope:",
                "",
                f"`{verified_runtime_evidence}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Investigation",
            "",
            f"- Status: `{_text(report.get('status'), 'unknown')}`",
            f"- Confidence: `{_text(report.get('confidence'), _text(root_cause.get('confidence'), 'unknown'))}`",
            f"- Target: `{_text(report.get('investigation_target'), 'unknown')}`",
            f"- Failure domain: `{_text(report.get('failure_domain'), 'unknown')}`",
            f"- Failure category: `{_text(report.get('failure_category'), 'unknown')}`",
            "",
        ]
    )

    _append_claim(lines, "Symptom", report.get("symptom"))
    _append_claim(lines, "Immediate Mechanism", report.get("immediate_mechanism"))

    if root_cause:
        lines.extend(["## Root Cause", "", _text(root_cause.get("claim")), ""])
        if root_cause.get("trigger"):
            lines.append(f"- **Trigger:** {_text(root_cause.get('trigger'))}")
        if root_cause.get("defect"):
            lines.append(f"- **Defect:** {_text(root_cause.get('defect'))}")
        lines.append(
            f"- **Confidence:** `{_text(report.get('confidence'), _text(root_cause.get('confidence'), 'unknown'))}`"
        )
        lines.extend(["", _text(root_cause.get("why")), ""])
        root_evidence = _references(root_cause.get("evidence_ids"))
        if root_evidence:
            lines.extend([f"Evidence: `{root_evidence}`", ""])

    causal_chain = report.get("causal_chain") or []
    if causal_chain:
        lines.extend(["## Causal Chain", ""])
        for index, item in enumerate(causal_chain, 1):
            evidence_ids = _references(item.get("evidence_ids"))
            suffix = f" (`{evidence_ids}`)" if evidence_ids else ""
            lines.append(
                f"{item.get('step', index)}. {_text(item.get('claim'))}{suffix}"
            )
        lines.append("")

    contribution = report.get("recorded_execution_contribution") or {}
    if contribution:
        lines.extend(
            [
                "## What The Recording Established",
                "",
                f"- **Contribution:** `{_text(contribution.get('classification'), 'unknown')}`",
                f"- **Decisive runtime fact:** {_text(contribution.get('decisive_runtime_fact'))}",
                "",
                _text(contribution.get("why")),
                "",
            ]
        )
        contribution_evidence = _references(contribution.get("evidence_ids"))
        if contribution_evidence:
            lines.extend([f"Evidence: `{contribution_evidence}`", ""])

    _append_claim(lines, "Violated Invariant", report.get("violated_invariant"))
    _append_claim(lines, "Control Flow", report.get("control_flow"))

    if reproducibility:
        lines.extend(
            [
                "## Reproducibility",
                "",
                f"- Determinism: `{_text(reproducibility.get('determinism'), 'unknown')}`",
                f"- Data dependency: `{_text(reproducibility.get('data_dependency'), 'unknown')}`",
                f"- Intermittency: `{_text(reproducibility.get('intermittency'), 'unknown')}`",
                f"- Confidence: `{_text(reproducibility.get('confidence'), 'unknown')}`",
                f"- Why: {_text(reproducibility.get('why'))}",
                "",
            ]
        )

    lines.extend(["## Runtime Evidence", ""])
    evidence = report.get("evidence") or []
    if not evidence:
        lines.extend(["No runtime evidence was reported.", ""])
    for index, item in enumerate(evidence, 1):
        evidence_id = _text(item.get("id"), str(index))
        lines.extend(
            [
                f"### Evidence {evidence_id}",
                "",
                f"- Claim: {_text(item.get('claim'))}",
                f"- Tool: `{_text(item.get('tool'), 'unknown')}`",
                f"- Replay coordinate: `{_evidence_location(item)}`",
                f"- Representation: `{_text(item.get('representation'), 'not reported')}`",
            ]
        )
        fact_ids = _references(item.get("fact_ids"))
        if fact_ids:
            lines.append(f"- Causal facts: `{fact_ids}`")
        lines.append("")
        _append_observed(lines, item.get("observed"))

    lines.extend(["## Replay Walkthrough", ""])
    walkthrough = report.get("replay_walkthrough") or []
    if not walkthrough:
        lines.append("No replay walkthrough was reported.")
    for index, item in enumerate(walkthrough, 1):
        evidence_ids = _references(item.get("evidence_ids"))
        suffix = f" (`{evidence_ids}`)" if evidence_ids else ""
        lines.append(
            f"{item.get('step', index)}. `{_text(item.get('action'), 'unknown')}`: "
            f"{_text(item.get('finding'))}{suffix}"
        )

    lines.extend(["", "## Suggested Fix", "", _text(suggested_fix.get("summary")), ""])
    files = suggested_fix.get("files") or []
    for item in files:
        path = _text(item.get("path"), "unknown path")
        line = item.get("line")
        location = f"{path}:{line}" if line not in (None, 0) else path
        lines.append(f"- `{location}`: {_text(item.get('change'))}")
    if not files:
        lines.append("- No file-level change was reported.")

    lines.extend(["", f"Recommended test: {_text(suggested_fix.get('test'))}", ""])
    if report.get("regression_condition"):
        lines.extend(
            [
                "## Regression Condition",
                "",
                _text(report.get("regression_condition")),
                "",
            ]
        )

    capability_defects = report.get("capability_defects") or []
    if capability_defects:
        lines.extend(["## Debugger Capability Defects", ""])
        for defect in capability_defects:
            lines.append(
                f"- **{_text(defect.get('capability'), 'unknown capability')}** "
                f"(`{_text(defect.get('status'), 'unknown')}`): "
                f"{_text(defect.get('observation'))} "
                f"Impact: {_text(defect.get('impact'))}"
            )
        lines.append("")

    _append_string_list(
        lines,
        "Unresolved Causal Links",
        report.get("unresolved_links"),
    )
    _append_string_list(
        lines,
        "Open Questions",
        report.get("open_questions"),
        show_empty=True,
    )
    _append_string_list(
        lines,
        "Limitations",
        report.get("limitations"),
        show_empty=True,
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_bug_report.py INPUT.json OUTPUT.md", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    try:
        payload = normalize_document(json.loads(input_path.read_text()))
    except (ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(payload))
    print(f"Rendered bug report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
