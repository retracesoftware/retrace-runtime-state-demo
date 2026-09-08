from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def require_any(text: str, label: str, values: tuple[str, ...], failures: list[str]) -> None:
    if not any(value.lower() in text for value in values):
        failures.append(f"missing {label}: expected one of {values}")


def normalize_artifact(document: dict) -> dict:
    if isinstance(document.get("report"), dict):
        return document
    if "status" in document and "title" in document:
        return {"report": document, "transcript": []}
    raise ValueError("structured AI report is missing report object")


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: validate_report.py REPORT.md PAYLOAD.json AI_REPORT.json",
            file=sys.stderr,
        )
        return 2

    report_path = Path(sys.argv[1])
    payload_path = Path(sys.argv[2])
    ai_report_path = Path(sys.argv[3])
    report = report_path.read_text().lower()
    payload = json.loads(payload_path.read_text())
    artifact = normalize_artifact(json.loads(ai_report_path.read_text()))
    ai_report = artifact["report"]
    transcript = json.dumps(artifact.get("transcript") or []).lower()
    bad_order = next(
        order
        for order in payload["orders"]
        if order["shipped_units"] == order["returned_units"]
    )

    failures: list[str] = []
    exact_values = {
        "gross revenue": bad_order["gross_revenue_cents"],
        "refunded revenue": bad_order["refunded_revenue_cents"],
        "net revenue": (
            bad_order["gross_revenue_cents"] - bad_order["refunded_revenue_cents"]
        ),
    }
    for label, value in exact_values.items():
        if str(value).lower() not in report:
            failures.append(f"missing {label}: {value}")
        if str(value).lower() not in transcript:
            failures.append(f"{label} is not supported by preserved DAP transcript: {value}")

    require_any(report, "exception", ("zerodivisionerror", "division by zero"), failures)
    require_any(
        report,
        "failure location",
        (
            "calculate_revenue_per_retained_unit",
            "test_unit_economics_report_contains_every_order",
            "order_metrics.py",
        ),
        failures,
    )
    require_any(report, "zero denominator", ("retained_units", "retained units"), failures)
    require_any(
        report,
        "practical fix",
        ("guard", "handle", "skip", "none", "null", "check", "conditional"),
        failures,
    )

    suggested_fix = ai_report.get("suggested_fix") or {}
    suggested_text = json.dumps(suggested_fix).lower()
    require_any(
        suggested_text,
        "explicit full-return policy",
        (
            "fully returned",
            "full return",
            "retained_units == 0",
            "retained_units > 0",
            "retained_units is zero",
            "retained units is zero",
        ),
        failures,
    )
    require_any(
        suggested_text,
        "domain-safe undefined-metric handling",
        ("skip", "not applicable", "none", "null"),
        failures,
    )
    if re.search(r"\breturn(?:ing)?\s+(?:a\s+)?(?:numeric\s+)?0\b", suggested_text):
        if not any(phrase in suggested_text for phrase in ("do not", "avoid", "unless")):
            failures.append(
                "suggested fix silently maps an undefined per-unit metric to numeric zero"
            )

    semantic_text = " ".join(
        str(value)
        for value in (
            ai_report.get("summary"),
            (ai_report.get("root_cause") or {}).get("claim"),
            (ai_report.get("root_cause") or {}).get("defect"),
            (ai_report.get("root_cause") or {}).get("trigger"),
            (ai_report.get("root_cause") or {}).get("why"),
        )
    ).lower()
    if any(
        phrase in semantic_text
        for phrase in ("incorrectly computed", "incorrectly set", "data is missing")
    ):
        failures.append(
            "report misclassifies the valid full-return arithmetic as incorrect or missing data"
        )

    suggested_files = suggested_fix.get("files") or []
    suggested_paths = [str(item.get("path", "")) for item in suggested_files]
    if not any(path.endswith("/app/order_metrics.py") for path in suggested_paths):
        failures.append(
            "suggested fix does not target the inspected production helper: "
            f"paths={suggested_paths}"
        )
    invented_paths = [
        path
        for path in suggested_paths
        if path
        and not path.endswith("/app/order_metrics.py")
        and not path.endswith("/tests/test_order_metrics.py")
    ]
    if invented_paths:
        failures.append(f"suggested fix cites unknown source path(s): {invented_paths}")

    for item in ai_report.get("evidence") or []:
        location = item.get("coordinate") or item.get("location") or {}
        if str(location.get("path", "")).endswith("/app/order_metrics.py"):
            if location.get("line") not in (None, 25):
                failures.append(
                    "production-source evidence cites the wrong division line: "
                    f"{location.get('line')} (expected 25)"
                )

    shipped = str(bad_order["shipped_units"])
    returned = str(bad_order["returned_units"])
    if shipped not in report or returned not in report:
        failures.append(
            "missing runtime shipped/returned values: "
            f"shipped={shipped}, returned={returned}"
        )
    if shipped not in transcript or returned not in transcript:
        failures.append(
            "runtime shipped/returned values are not supported by preserved DAP transcript: "
            f"shipped={shipped}, returned={returned}"
        )

    for item in ai_report.get("evidence") or []:
        observed = str(item.get("observed", "")).lower()
        for label, expected in (
            ("shipped_units", shipped),
            ("returned_units", returned),
        ):
            match = re.search(
                rf"{label.replace('_', '[_ ]')}\s*(?:=|:|is)\s*(\d+)",
                observed,
            )
            if match and match.group(1) != expected:
                failures.append(
                    f"AI evidence changed {label}: reported={match.group(1)} "
                    f"recorded={expected}"
                )

    if not re.search(r"retained(?:_units| units)?\s*(?:=|is|of|:)\s*0", report):
        failures.append("report does not state that retained_units is zero")

    if failures:
        print("Report quality validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Report quality validation passed.")
    print(f"- batch: {payload['batch_id']}")
    print(f"- order: {bad_order['order_id']}")
    print(f"- customer: {bad_order['customer_id']}")
    print(
        "- arithmetic: "
        f"shipped={bad_order['shipped_units']}, "
        f"returned={bad_order['returned_units']}, retained=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
