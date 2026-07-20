# ZeroDivisionError in Revenue Calculation

> Presentation rendering of the structured Retrace AI findings. No diagnostic claims have been added or rewritten.

## Summary

A division by zero occurred in the revenue calculation because `retained_units` was zero. Local variables at the failure point were inspected, confirming the exact runtime order and arithmetic that caused the failure.

## Investigation

- Status: `diagnosed`
- Target: `target_application`
- Failure domain: `target`
- Failure category: `target_exception`

## Root Cause

The denominator in the revenue-per-retained-unit calculation became zero because `shipped_units` and `returned_units` were both 24, so `retained_units = 24 - 24 = 0`.

Confidence: `high`

The local variable `retained_units` was directly read as zero at the failure line, confirming its role in the division error.

## Runtime Evidence

### Evidence 1

- Claim: Local variable `runtime_incident_evidence` identifies the runtime-created order and all arithmetic inputs that caused the failure.
- Tool: `get_variables`
- Location: `/app/tests/test_order_metrics.py, line 31`
- Observed: `batch_id=BATCH-6D1A5F2F80 order_id=ORD-76E9D644-0 customer_id=CUS-76856C shipped_units=24 returned_units=24 retained_units=0 gross_revenue_cents=59976 refunded_revenue_cents=55200 net_revenue_cents=4776`

### Evidence 2

- Claim: The inspected denominator confirms the `ZeroDivisionError`.
- Tool: `get_variables`
- Location: `/app/tests/test_order_metrics.py, line 31`
- Observed: `retained_units: 0`

## Replay Walkthrough

1. `get_variables`: Inspected local variables and identified the exact runtime order whose full return made `retained_units` zero.

## Reproducibility

- Confidence: `high`
- Determinism: `deterministic`
- Data dependency: `observed`
- Intermittency: `not_observed`
- Why: Retrace preserved the external API response and reproduced the failure from the recorded runtime values without calling the live service again.

## Suggested Fix

Handle fully returned orders before performing the division.

- `/app/app/order_metrics.py`: Add a guard that handles `retained_units == 0` before calculating revenue per retained unit.

Recommended test: Add a focused test for a fully returned order where shipped and returned quantities are equal.

## Open Questions

- None reported.

## Limitations

- None reported.
