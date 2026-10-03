"""Tests for PullRaptor report renderers (Markdown, JSON, SARIF)."""

import json
import time
import unittest

from pullraptor.models import (
    CoverageReceipt,
    Deadline,
    Diagnostic,
    Finding,
    FullReport,
    LimitFailure,
    RecordLimits,
    ReviewContract,
    ScopeEntry,
    Span,
)
from pullraptor.render import render_json, render_markdown, render_sarif


class TestRender(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = RecordLimits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    def _make_report(self, findings: tuple[Finding, ...] = ()) -> FullReport:
        contract = ReviewContract(
            base_tip="base123", comparison_base="base123", head="head123",
            policy_digest="pol123", config_digest="cfg123", tool_digest="tool123",
            profile="structural", expected_scope=(), discovery_complete=True,
        )
        return FullReport(
            schema="1", kind="full", contract=contract, receipts=(),
            inventory=("app.py",), exclusions=(), findings=findings,
            diagnostics=(), execution={"exit_code": 0},
        )

    def test_empty_findings_not_safety_claim(self) -> None:
        report = self._make_report(findings=())
        md = render_markdown(report, limits=self.limits, deadline=self.deadline)
        self.assertIn("No findings detected", md)
        self.assertIn("not a safety or correctness claim", md.lower())

    def test_unicode_sarif_character_columns(self) -> None:
        span = Span(
            path="app.py", side="head",
            start_line=1, end_line=1,
            start_byte=10, end_byte=18,
            start_column=5, end_column=11,
        )
        finding = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=span, claim="Mutable default argument", severity="advisory",
            policy_class="advisory", state="supported", witness="append(1)",
        )
        report = self._make_report(findings=(finding,))
        sarif_str = render_sarif(report, limits=self.limits, deadline=self.deadline)
        data = json.loads(sarif_str)

        self.assertEqual(data["version"], "2.1.0")
        results = data["runs"][0]["results"]
        self.assertEqual(len(results), 1)
        region = results[0]["locations"][0]["physicalLocation"]["region"]
        self.assertEqual(region["startLine"], 1)
        self.assertEqual(region["startColumn"], 5)
        self.assertEqual(region["endColumn"], 11)
        self.assertEqual(region["byteOffset"], 10)
        self.assertEqual(region["byteLength"], 8)

    def test_markdown_fence_html_link_breakout(self) -> None:
        # Witness with markdown fences and HTML
        bad_witness = "```python\n<script>alert('pwn')</script>\n[evil](https://evil.com)"
        span = Span(path="app.py", side="head", start_line=1, end_line=1, start_byte=0, end_byte=5, start_column=1, end_column=5)
        finding = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=span, claim="Claim", severity="advisory", policy_class="advisory",
            state="supported", witness=bad_witness,
        )
        report = self._make_report(findings=(finding,))
        md = render_markdown(report, limits=self.limits, deadline=self.deadline)
        # HTML tags should be escaped or stripped
        self.assertNotIn("<script>", md)

    def test_limit_failure_rendering_sarif(self) -> None:
        lf = LimitFailure(
            schema="1", kind="limit_failure",
            known_inputs={"base_tip": "b", "comparison_base": "b", "head": "h", "policy_digest": None, "reviewer_digest": None},
            exit_code=2, analysis_complete=False, details_omitted=True,
            cause="deadline_exceeded", limit={"name": "timeout", "cap": 60.0, "observed": 60.1},
            omitted_domains=({"domain": "findings", "count": None},),
        )
        sarif_str = render_sarif(lf, limits=self.limits, deadline=self.deadline)
        data = json.loads(sarif_str)
        self.assertEqual(data["runs"][0]["results"], [])
        self.assertFalse(data["runs"][0]["invocations"][0]["executionSuccessful"])


if __name__ == "__main__":
    unittest.main()
