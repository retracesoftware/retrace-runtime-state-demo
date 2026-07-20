from __future__ import annotations

import os
import time
from urllib.request import urlopen


health_url = os.environ.get("ORDERS_API_URL", "").replace(
    "/api/order-batches/current",
    "/health",
)

for attempt in range(30):
    try:
        with urlopen(health_url, timeout=2) as response:
            if response.status == 200:
                print(f"incident API ready: {health_url}")
                break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(1)
else:
    raise RuntimeError(f"incident API did not become ready: {health_url}")
