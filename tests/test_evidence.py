"""Tests for PullRaptor evidence accumulation, finding alignment, and policy decision."""

import unittest

from pullraptor.evidence import (
    accumulate,
    align_findings,
    decide,
    validate_receipts,
)
from pullraptor.models import (
    Config,
    CoverageReceipt,
    Diagnostic,
    Evidence,
    Finding,
    ReviewContract,
    ScopeEntry,
    Span,
)


class TestEvidence(unittest.TestCase):
    def test_all_evidence_accumulations(self) -> None:
        # 16 pair combinations for (s1, r1) and (s2, r2)
        states = [(False, False), (True, False), (False, True), (True, True)]
        for s1, r1 in states:
            for s2, r2 in states:
                with self.subTest(pair=((s1, r1), (s2, r2))):
                    e1 = Evidence(claim_key="k1", claim_type="py001", context="ctx", supported=s1, refuted=r1)
                    e2 = Evidence(claim_key="k1", claim_type="py001", context="ctx", supported=s2, refuted=r2)
                    res_s, res_r = accumulate((e1, e2))
                    self.assertEqual(res_s, s1 or s2)
                    self.assertEqual(res_r, r1 or r2)

    def test_different_claim_or_revision_cannot_accumulate(self) -> None:
        e1 = Evidence(claim_key="k1", claim_type="py001", context="rev1", supported=True, refuted=False)
        e2 = Evidence(claim_key="k2", claim_type="py001", context="rev2", supported=True, refuted=False)
        with self.assertRaises(ValueError):
            accumulate((e1, e2))

    def test_conflict_not_blocker(self) -> None:
        # Conflicted evidence cannot satisfy blocking policy
        contract = ReviewContract(
            base_tip="b", comparison_base="b", head="h",
            policy_digest="p", config_digest="c", tool_digest="t",
            profile="structural", expected_scope=(), discovery_complete=True,
        )
        span = Span("a.py", "head", 1, 1, 0, 10, 1, 10)
        finding = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=span, claim="claim", severity="error", policy_class="blocker",
            state="conflicted", witness="wit",
        )
        code = decide(contract, (), (finding,), (), Config())
        self.assertEqual(code, 0)  # Conflicted cannot block!

    def test_shifted_line_same_obligation(self) -> None:
        # Base finding on line 5, Head finding shifted to line 25 due to edits
        base_span = Span("a.py", "base", 5, 6, 40, 60, 1, 15)
        head_span = Span("a.py", "head", 25, 26, 240, 260, 1, 15)

        base_f = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=base_span, claim="claim", severity="advisory", policy_class="advisory",
            state="supported", witness="append(1)",
        )
        head_f = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=head_span, claim="claim", severity="advisory", policy_class="advisory",
            state="supported", witness="append(1)",
        )

        aligned = align_findings((base_f,), (head_f,), comparable=True)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].delta, "persisting")
        self.assertEqual(aligned[0].evidence_delta, "unchanged")

    def test_base_parse_failure_delta_unknown(self) -> None:
        head_span = Span("a.py", "head", 5, 6, 40, 60, 1, 15)
        head_f = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=head_span, claim="claim", severity="advisory", policy_class="advisory",
            state="supported", witness="append(1)",
        )
        # When baseline parsing failed, comparable is False
        aligned = align_findings((), (head_f,), comparable=False)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].delta, "unknown")
        self.assertEqual(aligned[0].evidence_delta, "unknown")

    def test_old_sink_new_witness_retained(self) -> None:
        span_b = Span("a.py", "base", 1, 2, 0, 20, 1, 10)
        span_h = Span("a.py", "head", 1, 2, 0, 20, 1, 10)
        base_f = Finding(
            rule="PY003", version="1.0", obligation="subprocess_shell", anchor="subprocess.run",
            span=span_b, claim="claim", severity="advisory", policy_class="advisory",
            state="supported", witness="subprocess.run('ls', shell=True)",
        )
        head_f = Finding(
            rule="PY003", version="1.0", obligation="subprocess_shell", anchor="subprocess.run",
            span=span_h, claim="claim", severity="advisory", policy_class="advisory",
            state="supported", witness="subprocess.run('rm -rf', shell=True)",
        )
        aligned = align_findings((base_f,), (head_f,), comparable=True)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0].delta, "persisting")
        self.assertEqual(aligned[0].evidence_delta, "changed")

    def test_missing_receipt_cannot_complete(self) -> None:
        scope = (
            ScopeEntry(key="file:head:612e7079:python_patterns", kind="file", snapshot="head", capability="python_patterns"),
        )
        contract = ReviewContract(
            base_tip="b", comparison_base="b", head="h",
            policy_digest="p123", config_digest="c", tool_digest="t",
            profile="structural", expected_scope=scope, discovery_complete=True,
        )
        # Empty receipts
        diags = validate_receipts(contract, ())
        self.assertTrue(any(d.code == "MISSING_RECEIPT" for d in diags))

        code = decide(contract, (), (), diags, Config())
        self.assertEqual(code, 2)

    def test_duplicate_or_foreign_receipt_rejected(self) -> None:
        scope = (
            ScopeEntry(key="file:head:612e7079:python_patterns", kind="file", snapshot="head", capability="python_patterns"),
        )
        contract = ReviewContract(
            base_tip="b", comparison_base="b", head="h",
            policy_digest="p123", config_digest="c", tool_digest="t",
            profile="structural", expected_scope=scope, discovery_complete=True,
        )
        r1 = CoverageReceipt(key="file:head:612e7079:python_patterns", contract_digest="p123", capability="python_patterns", status="complete")
        r2 = CoverageReceipt(key="file:head:612e7079:python_patterns", contract_digest="p123", capability="python_patterns", status="complete")
        r_foreign = CoverageReceipt(key="foreign:key", contract_digest="p123", capability="python_patterns", status="complete")

        diags = validate_receipts(contract, (r1, r2, r_foreign))
        self.assertTrue(any(d.code == "DUPLICATE_RECEIPT" for d in diags))
        self.assertTrue(any(d.code == "FOREIGN_RECEIPT" for d in diags))

    def test_fatal_diagnostic_exit3(self) -> None:
        contract = ReviewContract(
            base_tip="b", comparison_base="b", head="h",
            policy_digest="p", config_digest="c", tool_digest="t",
            profile="structural", expected_scope=(), discovery_complete=True,
        )
        diag = Diagnostic(code="TOOL_ERROR", message="Git executable failed", cause="tool_failure")
        code = decide(contract, (), (), (diag,), Config())
        self.assertEqual(code, 3)

    def test_incomplete_precedes_finding_exit(self) -> None:
        scope = (
            ScopeEntry(key="file:head:612e7079:python_patterns", kind="file", snapshot="head", capability="python_patterns"),
        )
        contract = ReviewContract(
            base_tip="b", comparison_base="b", head="h",
            policy_digest="p123", config_digest="c", tool_digest="t",
            profile="structural", expected_scope=scope, discovery_complete=False,
        )
        receipt = CoverageReceipt(key="file:head:612e7079:python_patterns", contract_digest="p123", capability="python_patterns", status="incomplete")
        span = Span("a.py", "head", 1, 1, 0, 10, 1, 10)
        finding = Finding(
            rule="PY001", version="1.0", obligation="mut_default", anchor="x",
            span=span, claim="claim", severity="error", policy_class="blocker",
            state="supported", witness="append(1)",
        )
        # Even with a blocker, incomplete analysis returns 2 first!
        code = decide(contract, (receipt,), (finding,), (), Config())
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
