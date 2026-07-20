from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _text(value: Any, fallback: str = "Not provided.") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


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


def render(payload: dict[str, Any]) -> str:
    report = payload["report"]
    root_cause = report.get("root_cause") or {}
    reproducibility = report.get("reproducibility") or {}
    suggested_fix = report.get("suggested_fix") or {}
    lines = [
        f"# {_text(report.get('title'), 'Retrace AI Debug Report')}",
        "",
        "> Presentation rendering of the structured Retrace AI findings. "
        "No diagnostic claims have been added or rewritten.",
        "",
        "## Summary",
        "",
        _text(report.get("summary")),
        "",
        "## Investigation",
        "",
        f"- Status: `{_text(report.get('status'), 'unknown')}`",
        f"- Target: `{_text(report.get('investigation_target'), 'unknown')}`",
        f"- Failure domain: `{_text(report.get('failure_domain'), 'unknown')}`",
        f"- Failure category: `{_text(report.get('failure_category'), 'unknown')}`",
        "",
        "## Root Cause",
        "",
        _text(root_cause.get("claim")),
        "",
        f"Confidence: `{_text(root_cause.get('confidence'), 'unknown')}`",
        "",
        _text(root_cause.get("why")),
        "",
        "## Runtime Evidence",
        "",
    ]

    evidence = report.get("evidence") or []
    if not evidence:
        lines.append("No runtime evidence was reported.")
    for index, item in enumerate(evidence, 1):
        lines.extend(
            [
                f"### Evidence {index}",
                "",
                f"- Claim: {_text(item.get('claim'))}",
                f"- Tool: `{_text(item.get('tool'), 'unknown')}`",
                f"- Location: `{_location(item.get('location') or {})}`",
                f"- Observed: `{_text(item.get('observed'))}`",
                "",
            ]
        )

    lines.extend(["## Replay Walkthrough", ""])
    walkthrough = report.get("replay_walkthrough") or []
    if not walkthrough:
        lines.append("No replay walkthrough was reported.")
    for item in walkthrough:
        lines.append(
            f"{item.get('step', '?')}. `{_text(item.get('action'), 'unknown')}`: "
            f"{_text(item.get('finding'))}"
        )

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            f"- Confidence: `{_text(reproducibility.get('confidence'), 'unknown')}`",
            f"- Determinism: `{_text(reproducibility.get('determinism'), 'unknown')}`",
            f"- Data dependency: `{_text(reproducibility.get('data_dependency'), 'unknown')}`",
            f"- Intermittency: `{_text(reproducibility.get('intermittency'), 'unknown')}`",
            f"- Why: {_text(reproducibility.get('why'))}",
            "",
            "## Suggested Fix",
            "",
            _text(suggested_fix.get("summary")),
            "",
        ]
    )

    files = suggested_fix.get("files") or []
    for item in files:
        # Model-proposed line numbers are advisory and may not refer to an
        # inspected source line. Keep the file and proposed change in the
        # presentation; the untouched structured JSON preserves every field.
        path = _text(item.get("path"), "unknown path")
        lines.append(f"- `{path}`: {_text(item.get('change'))}")
    if not files:
        lines.append("- No file-level change was reported.")

    lines.extend(
        [
            "",
            f"Recommended test: {_text(suggested_fix.get('test'))}",
            "",
            "## Open Questions",
            "",
        ]
    )
    open_questions = report.get("open_questions") or []
    if open_questions:
        lines.extend(f"- {_text(question)}" for question in open_questions)
    else:
        lines.append("- None reported.")

    lines.extend(["", "## Limitations", ""])
    limitations = report.get("limitations") or []
    if limitations:
        lines.extend(f"- {_text(limitation)}" for limitation in limitations)
    else:
        lines.append("- None reported.")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: render_presentation_report.py INPUT.json OUTPUT.md",
            file=sys.stderr,
        )
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    payload = json.loads(input_path.read_text())
    if not isinstance(payload.get("report"), dict):
        print("structured AI report is missing report object", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(payload))
    print(f"Rendered presentation report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
