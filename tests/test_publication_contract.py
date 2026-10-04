"""Tests for publication context binding (E02-A2)."""

from __future__ import annotations

import unittest

from pullraptor.models import Finding, FullReport, LimitFailure, ReviewContract, ScopeEntry, Span
from pullraptor.publication_contract import PublicationContext, scope_digest_from_report, validate_publication

_HEAD = "a" * 40
_BASE = "b" * 40
_COMP = "c" * 40


def _context_for_report(report: FullReport, **overrides: object) -> PublicationContext:
    base = {
        "repository_id": "owner/repo",
        "pr_number": 7,
        "workflow_id": "wf-1",
        "run_id": "run-1",
        "artifact_digest": "art-digest",
        "reviewer_digest": "rev-digest",
        "head": _HEAD,
        "base_tip": _BASE,
        "comparison_base": _COMP,
        "policy_digest": report.contract.policy_digest,
        "scope_digest": scope_digest_from_report(report),
    }
    base.update(overrides)
    return PublicationContext(**base)


def _full_report(*, findings: tuple[Finding, ...] = (), **contract_overrides: object) -> FullReport:
    contract_fields = {
        "base_tip": _BASE,
        "comparison_base": _COMP,
        "head": _HEAD,
        "policy_digest": "policy-a",
        "config_digest": "cfg",
        "tool_digest": "tool",
        "profile": "structural",
        "expected_scope": (),
        "discovery_complete": True,
    }
    contract_fields.update(contract_overrides)
    contract = ReviewContract(**contract_fields)
    return FullReport(
        schema="1",
        kind="full",
        contract=contract,
        receipts=(),
        inventory=("app.py",),
        findings=findings,
        diagnostics=(),
        execution={"exit_code": 0},
    )


class TestPublicationContract(unittest.TestCase):
    def test_base_policy_changed_same_head(self) -> None:
        report = _full_report()
        expected = _context_for_report(report)
        current = _context_for_report(report, policy_digest="policy-b")
        decision = validate_publication(report, expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "stale_policy")
        self.assertEqual(decision.inline_keys, ())

    def test_cross_pr_replay(self) -> None:
        report = _full_report()
        expected = _context_for_report(report, pr_number=1)
        current = _context_for_report(report, pr_number=2)
        decision = validate_publication(report, expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "cross_pr_replay")

    def test_wrong_workflow_run_artifact(self) -> None:
        report = _full_report()
        expected = _context_for_report(report, run_id="run-1")
        current = _context_for_report(report, run_id="run-2")
        decision = validate_publication(report, expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "wrong_workflow_run_artifact")

    def test_missing_or_prefix_head_denied(self) -> None:
        report = _full_report()
        expected = _context_for_report(report, head="deadbeef")
        current = _context_for_report(report, head="deadbeef")
        decision = validate_publication(report, expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "invalid_head")

    def test_deleted_side_location(self) -> None:
        finding = Finding(
            rule="PY001",
            version="1",
            obligation="ob1",
            anchor="a1",
            span=Span(
                path="removed.py",
                side="head",
                start_line=1,
                end_line=1,
                start_byte=0,
                end_byte=1,
                start_column=1,
                end_column=2,
            ),
            claim="claim",
            severity="low",
            policy_class="advisory",
            state="undetermined",
            witness="w1",
        )
        report = _full_report()
        report = FullReport(
            schema=report.schema,
            kind=report.kind,
            contract=report.contract,
            receipts=report.receipts,
            inventory=("app.py",),
            findings=(finding,),
            diagnostics=report.diagnostics,
            execution=report.execution,
        )
        ctx = _context_for_report(report)
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "deleted_side_location")

    def test_report_contract_context_mismatch_denied(self) -> None:
        report = _full_report()
        expected = _context_for_report(report)
        tampered = FullReport(
            schema=report.schema,
            kind=report.kind,
            contract=ReviewContract(
                base_tip=report.contract.base_tip,
                comparison_base=report.contract.comparison_base,
                head=report.contract.head,
                policy_digest="other-policy",
                config_digest=report.contract.config_digest,
                tool_digest=report.contract.tool_digest,
                profile=report.contract.profile,
                expected_scope=report.contract.expected_scope,
                discovery_complete=True,
            ),
            receipts=report.receipts,
            inventory=report.inventory,
            findings=report.findings,
            diagnostics=report.diagnostics,
            execution=report.execution,
        )
        ctx = _context_for_report(report)
        decision = validate_publication(tampered, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "report_contract_context_mismatch")

    def test_incomplete_receipts_no_inline(self) -> None:
        scope = ScopeEntry(
            key="file:tree:6170702e7079:structural",
            kind="file",
            snapshot="tree",
            capability="structural",
            path="app.py",
            path_bytes=b"app.py",
        )
        contract = ReviewContract(
            base_tip=_BASE,
            comparison_base=_COMP,
            head=_HEAD,
            policy_digest="policy-a",
            config_digest="cfg",
            tool_digest="tool",
            profile="structural",
            expected_scope=(scope,),
            discovery_complete=True,
        )
        report = FullReport(
            schema="1",
            kind="full",
            contract=contract,
            receipts=(),
            inventory=("app.py",),
            findings=(),
            diagnostics=(),
            execution={"exit_code": 0},
        )
        ctx = _context_for_report(report)
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "incomplete_receipts")
        self.assertEqual(decision.inline_keys, ())

    def test_scope_capability_revision_collision_denied(self) -> None:
        scope = ScopeEntry(
            key="file:tree:6170702e7079:structural",
            kind="file",
            snapshot="tree",
            capability="structural",
            path="app.py",
            path_bytes=b"app.py",
        )
        report = _full_report(expected_scope=(scope,))
        ctx = _context_for_report(report, scope_digest="0" * 64)
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "scope_capability_revision_collision")

    def test_invalid_side_range_or_deleted_location_denied(self) -> None:
        finding = Finding(
            rule="PY001",
            version="1",
            obligation="ob1",
            anchor="a1",
            span=Span(
                path="app.py",
                side="base",
                start_line=1,
                end_line=1,
                start_byte=0,
                end_byte=1,
                start_column=1,
                end_column=2,
            ),
            claim="claim",
            severity="low",
            policy_class="advisory",
            state="undetermined",
            witness="w1",
        )
        report = _full_report(findings=(finding,))
        ctx = _context_for_report(report)
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "invalid_side_location")

    def test_limit_failure_no_inline(self) -> None:
        report = LimitFailure(
            schema="1",
            kind="limit_failure",
            known_inputs={"head": _HEAD},
            exit_code=2,
            analysis_complete=False,
            details_omitted=True,
            cause="timeout",
        )
        report_ctx = _full_report()
        ctx = _context_for_report(report_ctx)
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "limit_failure")
        self.assertEqual(decision.inline_keys, ())

    def test_current_exact_context_authorized(self) -> None:
        report = _full_report()
        ctx = _context_for_report(report)
        decision = validate_publication(report, ctx, ctx)
        self.assertTrue(decision.authorized)
        self.assertEqual(decision.cause, "authorized")


if __name__ == "__main__":
    unittest.main()
