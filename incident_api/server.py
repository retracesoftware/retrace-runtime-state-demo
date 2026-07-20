from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


STATE_DIR = Path(os.environ.get("INCIDENT_STATE_DIR", "/state"))
REQUEST_COUNT_PATH = STATE_DIR / "request-count.txt"
LATEST_PAYLOAD_PATH = STATE_DIR / "latest-payload.json"


def _read_request_count() -> int:
    try:
        return int(REQUEST_COUNT_PATH.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _new_order(*, index: int, full_return: bool = False) -> dict[str, Any]:
    shipped_units = secrets.choice((8, 12, 16, 24))
    returned_units = shipped_units if full_return else secrets.choice((0, 1, 2))
    unit_price_cents = secrets.choice((1299, 1899, 2499, 3299))
    gross_revenue_cents = shipped_units * unit_price_cents
    refund_per_unit_cents = max(unit_price_cents - 199, 1)
    refunded_revenue_cents = returned_units * refund_per_unit_cents
    return {
        "order_id": f"ORD-{secrets.token_hex(4).upper()}-{index}",
        "customer_id": f"CUS-{secrets.token_hex(3).upper()}",
        "shipped_units": shipped_units,
        "returned_units": returned_units,
        "gross_revenue_cents": gross_revenue_cents,
        "refunded_revenue_cents": refunded_revenue_cents,
    }


def _build_runtime_payload() -> dict[str, Any]:
    return {
        "batch_id": f"BATCH-{secrets.token_hex(5).upper()}",
        "generated_at": datetime.now(UTC).isoformat(),
        "orders": [
            _new_order(index=0, full_return=True),
            _new_order(index=1),
            _new_order(index=2),
        ],
    }


class IncidentHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if self.path != "/api/order-batches/current":
            self._send_json(404, {"error": "not found"})
            return

        payload = _build_runtime_payload()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        REQUEST_COUNT_PATH.write_text(f"{_read_request_count() + 1}\n")
        LATEST_PAYLOAD_PATH.write_text(json.dumps(payload, indent=2) + "\n")
        self._send_json(200, payload)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"incident-api: {format % args}", flush=True)


if __name__ == "__main__":
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("0.0.0.0", 8080), IncidentHandler)
    print("single-threaded incident API listening on :8080", flush=True)
    server.serve_forever()
