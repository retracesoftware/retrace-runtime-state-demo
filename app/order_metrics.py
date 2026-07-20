from __future__ import annotations

import os
from typing import Any

import requests


ORDERS_API_URL = os.environ.get(
    "ORDERS_API_URL",
    "http://127.0.0.1:8080/api/order-batches/current",
)


def fetch_current_order_batch() -> dict[str, Any]:
    response = requests.get(ORDERS_API_URL, timeout=5)
    response.raise_for_status()
    return response.json()


def calculate_revenue_per_retained_unit(
    net_revenue_cents: int,
    retained_units: int,
) -> float:
    return round(net_revenue_cents / retained_units, 2)
