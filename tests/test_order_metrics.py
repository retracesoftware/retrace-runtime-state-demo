from app.order_metrics import (
    calculate_revenue_per_retained_unit,
    fetch_current_order_batch,
)


def test_unit_economics_report_contains_every_order() -> None:
    payload = fetch_current_order_batch()
    batch_id = payload["batch_id"]
    orders = payload["orders"]
    report_rows = []

    for order_position, order in enumerate(orders):
        order_id = order["order_id"]
        customer_id = order["customer_id"]
        shipped_units = int(order["shipped_units"])
        returned_units = int(order["returned_units"])
        retained_units = shipped_units - returned_units
        gross_revenue_cents = int(order["gross_revenue_cents"])
        refunded_revenue_cents = int(order["refunded_revenue_cents"])
        net_revenue_cents = gross_revenue_cents - refunded_revenue_cents
        runtime_incident_evidence = (
            f"batch_id={batch_id} order_id={order_id} customer_id={customer_id} "
            f"shipped_units={shipped_units} returned_units={returned_units} "
            f"retained_units={retained_units} "
            f"gross_revenue_cents={gross_revenue_cents} "
            f"refunded_revenue_cents={refunded_revenue_cents} "
            f"net_revenue_cents={net_revenue_cents}"
        )

        revenue_per_retained_unit = calculate_revenue_per_retained_unit(
            net_revenue_cents,
            retained_units,
        )
        report_rows.append(
            {
                "batch_id": batch_id,
                "order_position": order_position,
                "order_id": order_id,
                "customer_id": customer_id,
                "retained_units": retained_units,
                "net_revenue_cents": net_revenue_cents,
                "runtime_incident_evidence": runtime_incident_evidence,
                "revenue_per_retained_unit": revenue_per_retained_unit,
            }
        )

    assert len(report_rows) == 3
