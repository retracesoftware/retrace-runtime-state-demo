from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.render_bug_report import normalize_document, render


ROOT = Path(__file__).resolve().parents[1]


def report_fixture() -> dict:
    evidence_value = (
        "batch_id=BATCH-TEST order_id=ORDER-TEST customer_id=CUSTOMER-TEST "
        "shipped_units=8 returned_units=8 retained_units=0 "
        "gross_revenue_cents=19992 refunded_revenue_cents=18400 "
        "net_revenue_cents=1592"
    )
    return {
        "report": {
            "status": "diagnosed",
            "confidence": "high",
            "investigation_target": "target_application",
            "failure_domain": "target",
            "failure_category": "target_exception",
            "title": "ZeroDivisionError in revenue calculation",
            "summary": (
                "A full return produced shipped_units=8, returned_units=8, "
                "retained_units=0, gross_revenue_cents=19992, "
                "refunded_revenue_cents=18400, and net_revenue_cents=1592. "
                "The production helper divided by the zero retained-unit count."
            ),
            "symptom": {
                "claim": "ZeroDivisionError was raised at the revenue division.",
                "evidence_ids": ["E1"],
            },
            "immediate_mechanism": {
                "claim": "net_revenue_cents was divided by retained_units=0.",
                "evidence_ids": ["E1", "E2"],
            },
            "root_cause": {
                "claim": "The helper does not handle a valid fully returned order.",
                "trigger": "shipped_units=8 and returned_units=8 produced retained_units=0.",
                "defect": "The per-unit division has no zero-retained-units policy.",
                "why": "Replay connected the full-return inputs to the zero divisor.",
                "evidence_ids": ["E1", "E2"],
            },
            "causal_chain": [
                {
                    "step": 1,
                    "claim": "The order was fully returned.",
                    "evidence_ids": ["E1"],
                },
                {
                    "step": 2,
                    "claim": "retained_units became zero and was used as a divisor.",
                    "evidence_ids": ["E1", "E2"],
                },
            ],
            "recorded_execution_contribution": {
                "classification": "essential",
                "decisive_runtime_fact": evidence_value,
                "why": "The identifiers and arithmetic existed only in the recorded response.",
                "evidence_ids": ["E1"],
            },
            "violated_invariant": None,
            "control_flow": {
                "claim": "Every order reached the unguarded metric calculation.",
                "evidence_ids": ["E2"],
            },
            "reproducibility": {
                "data_dependency": "observed",
                "intermittency": "not_observed",
                "determinism": "deterministic",
                "confidence": "high",
                "why": "Replay restored the same external API response.",
            },
            "suggested_fix": {
                "summary": (
                    "Handle a fully returned order before division by skipping the "
                    "undefined metric or representing it as None/not applicable."
                ),
                "files": [
                    {
                        "path": "/app/app/order_metrics.py",
                        "line": 25,
                        "change": "Return None for this metric when retained_units == 0.",
                    }
                ],
                "test": "Add a regression for a full return with retained_units == 0.",
            },
            "regression_condition": (
                "A fully returned order must not enter the per-retained-unit division."
            ),
            "capability_defects": [],
            "unresolved_links": [],
            "evidence": [
                {
                    "id": "E1",
                    "claim": "Historical locals contain the complete order arithmetic.",
                    "tool": "get_variables",
                    "coordinate": {
                        "thread_id": 1,
                        "message_index": 1713,
                        "cursor": {"function_counts": [1, 2], "f_lasti": 42},
                        "path": "/app/tests/test_order_metrics.py",
                        "line": 31,
                        "function": "test_unit_economics_report_contains_every_order",
                    },
                    "representation": "literal",
                    "fact_ids": ["F1"],
                    "observed": evidence_value,
                },
                {
                    "id": "E2",
                    "claim": "Source performs the unguarded division.",
                    "tool": "get_source_context",
                    "coordinate": {
                        "thread_id": 1,
                        "message_index": 1713,
                        "cursor": None,
                        "path": "/app/app/order_metrics.py",
                        "line": 25,
                        "function": "calculate_revenue_per_retained_unit",
                    },
                    "representation": "source",
                    "observed": "return round(net_revenue_cents / retained_units, 2)",
                },
            ],
            "replay_walkthrough": [
                {
                    "step": 1,
                    "action": "get_variables",
                    "finding": "Observed the full-return arithmetic.",
                    "evidence_ids": ["E1"],
                }
            ],
            "open_questions": [],
            "limitations": [],
        },
        "transcript": [
            {
                "tool": "get_variables",
                "result": {
                    "data": {
                        "variables": [
                            {
                                "name": "runtime_incident_evidence",
                                "value": repr(evidence_value),
                            }
                        ]
                    }
                },
            }
        ],
    }


def payload_fixture() -> dict:
    return {
        "batch_id": "BATCH-TEST",
        "orders": [
            {
                "order_id": "ORDER-TEST",
                "customer_id": "CUSTOMER-TEST",
                "shipped_units": 8,
                "returned_units": 8,
                "gross_revenue_cents": 19992,
                "refunded_revenue_cents": 18400,
            }
        ],
    }


class ReportRendererTests(unittest.TestCase):
    def test_renders_v2_causal_report_as_human_readable_markdown(self) -> None:
        markdown = render(report_fixture())

        for expected in (
            "## Symptom",
            "## Immediate Mechanism",
            "## Root Cause",
            "**Trigger:** shipped_units=8",
            "**Defect:** The per-unit division has no zero-retained-units policy.",
            "## Causal Chain",
            "## What The Recording Established",
            "## Control Flow",
            "## Runtime Evidence",
            "### Evidence E1",
            "/app/tests/test_order_metrics.py:31",
            "## Regression Condition",
        ):
            self.assertIn(expected, markdown)

    def test_accepts_a_bare_v2_report(self) -> None:
        report = report_fixture()["report"]
        normalized = normalize_document(report)

        self.assertIs(normalized["report"], report)
        self.assertEqual(normalized["transcript"], [])

    def test_renders_degraded_debugger_capability(self) -> None:
        artifact = report_fixture()
        artifact["report"]["capability_defects"] = [
            {
                "capability": "variables",
                "status": "degraded",
                "observation": "A value rendered as <repr failed>.",
                "impact": "The producer value could not be inspected.",
                "causal_impact": "partial",
                "affected_causal_link": "producer of retained_units",
            }
        ]

        markdown = render(artifact)

        self.assertIn("## Debugger Capability Defects", markdown)
        self.assertIn("<repr failed>", markdown)

    def test_quality_gate_accepts_domain_safe_v2_report(self) -> None:
        completed = self._run_validator(report_fixture())

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Report quality validation passed.", completed.stdout)

    def test_quality_gate_rejects_value_error_only_policy(self) -> None:
        artifact = copy.deepcopy(report_fixture())
        artifact["report"]["suggested_fix"] = {
            "summary": "Raise ValueError when retained_units == 0.",
            "files": [
                {
                    "path": "/app/app/order_metrics.py",
                    "line": 25,
                    "change": "Raise ValueError for retained_units == 0.",
                }
            ],
            "test": "Assert ValueError for a full return.",
        }

        completed = self._run_validator(artifact)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("domain-safe undefined-metric handling", completed.stderr)

    def _run_validator(self, artifact: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.md"
            payload_path = root / "payload.json"
            artifact_path = root / "artifact.json"
            report_path.write_text(render(artifact))
            payload_path.write_text(json.dumps(payload_fixture()))
            artifact_path.write_text(json.dumps(artifact))
            return subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_report.py"),
                    str(report_path),
                    str(payload_path),
                    str(artifact_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
