# Retrace Runtime-State Demo

This repository is a self-contained introduction to Retrace. It demonstrates
both parts of the product:

1. Record a real pytest failure and generate an evidence-backed AI report.
2. Open a preserved recording in VS Code and inspect the historical runtime
   state with the Retrace time-travel debugger.

No application code, database, or API key is required. Docker provides the
complete Python and Retrace environment.

## What The Demo Shows

The application fetches a freshly generated order batch from an external HTTP
API. One order is fully returned, so its runtime values satisfy:

```text
retained_units = shipped_units - returned_units
retained_units = 24 - 24 = 0
```

The application divides net revenue by `retained_units` and raises
`ZeroDivisionError`.

Source analysis can warn that the denominator might become zero. It cannot
identify the runtime-created batch, order, customer, quantities, and financial
values that caused a particular incident. Retrace records that external API
response and later reproduces the same failure without calling the API again.

## Requirements

- Docker Desktop or Docker Engine with Docker Compose
- Internet access for the live hosted-AI path
- VS Code and its Dev Containers extension for the visual debugger path

The demo works on macOS and Linux hosts supported by Docker.

## Get The Demo

```bash
git clone https://github.com/retracesoftware/retrace-runtime-state-demo.git
cd retrace-runtime-state-demo
```

## Path 1: Generate A Fresh AI Report

Prepare the images and start the small incident API:

```bash
make prepare
```

Run the complete demonstration:

```bash
make convention
```

The command performs this real product workflow:

```text
fresh external API response
  -> pytest failure
  -> Retrace recording
  -> deterministic DAP replay
  -> runtime-variable inspection
  -> hosted AI report
  -> direct replay with the API request counter unchanged
```

The underlying recording command is:

```bash
RETRACE_AUTO_DEBUG=1 \
retracepython --recording /app/recordings/runtime-incident.retrace \
  -m pytest -vs tests
```

No `RETRACE_API_KEY` is required for the default hosted allowance. The run is
successful only when the report identifies the exact runtime order and
arithmetic, direct replay reproduces the same exception, and recording plus
both replay paths make exactly one live API request in total.

Generated files are written to:

```text
reports/runtime-incident.presentation.md
reports/runtime-incident.ai-report.md
reports/runtime-incident.ai-report.json
reports/runtime-payload.json
recordings/runtime-incident.retrace
```

Open the latest presentation report again with:

```bash
make report
```

A reviewed example is available at
[`example-reports/runtime-incident.presentation.md`](example-reports/runtime-incident.presentation.md).

## Path 2: Inspect A Recording In VS Code

This path uses the reviewed recording at
`debug-recording/runtime-state.retrace`. It does not call the incident API,
consume a hosted AI session, or require internet after the Dev Container image
has been built.

Install the VS Code Dev Containers extension if needed:

```bash
code --install-extension ms-vscode-remote.remote-containers
```

Open the repository:

```bash
code .
```

In VS Code:

1. Open the Command Palette.
2. Run **Dev Containers: Reopen in Container**.
3. Wait for the image and remote extensions to finish installing.
4. Open `/app/tests/test_order_metrics.py`.
5. Set a breakpoint on line 31 at the call to
   `calculate_revenue_per_retained_unit`.
6. Open the Retrace sidebar in the activity bar.
7. Click play on `python (PID ...)`.
8. Press Continue after the initial entry stop.
9. At the breakpoint, inspect Locals.

The important preserved values are:

```text
shipped_units = 24
returned_units = 24
retained_units = 0
net_revenue_cents = 4776
runtime_incident_evidence = "batch_id=... order_id=... customer_id=..."
```

The Dev Container installs the Retrace extension in the remote workspace and
selects the bundled recording automatically. Its reviewed diagnosis is
[`debug-report/runtime-state.md`](debug-report/runtime-state.md).

## Verify The Visual Debugger Without Clicking

From the Dev Container terminal, run:

```bash
python /app/scripts/verify_debugger.py --all
```

Or run the VS Code task **Retrace: verify runtime-state recording**.

The verifier checks:

- exact Python and Retrace package versions
- recording and replay-binary availability
- direct replay of the expected `ZeroDivisionError`
- DAP initialization and launch
- verified breakpoint discovery
- entry and breakpoint stops
- the expected source frame
- scopes and useful local variables

The same verification can be run from the host:

```bash
make debugger-verify
```

## Why The Trace Matters

Every live run receives different identifiers and financial values. Within one
recording, however, the AI debugger and direct replay observe the exact values
captured during the original failure. The external API is not contacted again.

That lets a developer answer:

```text
Which real request caused the failure?
Which order and customer were affected?
What were the exact arithmetic inputs?
Can the incident still be reproduced after the external data changes?
Can locals that were never logged be inspected later?
```

## Reset

Remove live-demo containers and generated outputs:

```bash
make clean
```

Remove the standalone debugger verification container:

```bash
make debugger-clean
```

The bundled recording and reviewed example reports are not removed.

## Versions

The demo currently uses:

```text
Python 3.12
retracesoftware 0.2.25
retracesoftware-dap 0.2.25
```

## License

Apache-2.0. See [LICENSE](LICENSE).
