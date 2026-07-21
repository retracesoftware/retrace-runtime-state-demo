from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def expected_evidence(payload: dict[str, Any]) -> str:
    order = next(
        item
        for item in payload["orders"]
        if int(item["shipped_units"]) == int(item["returned_units"])
    )
    retained = int(order["shipped_units"]) - int(order["returned_units"])
    net = int(order["gross_revenue_cents"]) - int(order["refunded_revenue_cents"])
    return (
        f"batch_id={payload['batch_id']} order_id={order['order_id']} "
        f"customer_id={order['customer_id']} "
        f"shipped_units={order['shipped_units']} "
        f"returned_units={order['returned_units']} retained_units={retained} "
        f"gross_revenue_cents={order['gross_revenue_cents']} "
        f"refunded_revenue_cents={order['refunded_revenue_cents']} "
        f"net_revenue_cents={net}"
    )


def observed_runtime_evidence(artifact: dict[str, Any]) -> list[str]:
    observed: list[str] = []
    for entry in artifact.get("transcript") or []:
        if entry.get("tool") != "get_variables":
            continue
        variables = (
            ((entry.get("result") or {}).get("data") or {}).get("variables") or []
        )
        for variable in variables:
            if variable.get("name") == "runtime_incident_evidence":
                observed.append(str(variable.get("value", "")).strip("'\""))
    return observed


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: extract_verified_runtime_evidence.py AI_REPORT.json PAYLOAD.json",
            file=sys.stderr,
        )
        return 2

    artifact = json.loads(Path(sys.argv[1]).read_text())
    payload = json.loads(Path(sys.argv[2]).read_text())
    expected = expected_evidence(payload)
    observations = observed_runtime_evidence(artifact)
    if not any(expected in item for item in observations):
        print(
            "AI transcript does not contain runtime_incident_evidence matching "
            "the recorded payload",
            file=sys.stderr,
        )
        return 1

    print(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
