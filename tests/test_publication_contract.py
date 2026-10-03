"""Tests for publication context binding (E02-A2)."""

from __future__ import annotations

import unittest

from pullraptor.models import Finding, FullReport, LimitFailure, ReviewContract, Span
from pullraptor.publication_contract import PublicationContext, validate_publication

_HEAD = "a" * 40
_BASE = "b" * 40
_COMP = "c" * 40


def _context(**overrides: object) -> PublicationContext:
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
        "policy_digest": "policy-a",
        "scope_digest": "scope-a",
    }
    base.update(overrides)
    return PublicationContext(**base)


def _full_report(**contract_overrides: object) -> FullReport:
    contract = ReviewContract(
        base_tip=_BASE,
        comparison_base=_COMP,
        head=_HEAD,
        policy_digest="policy-a",
        config_digest="cfg",
        tool_digest="tool",
        profile="structural",
        expected_scope=(),
        discovery_complete=True,
    )
    return FullReport(
        schema="1",
        kind="full",
        contract=contract,
        receipts=(),
        inventory=("app.py",),
        findings=(),
        diagnostics=(),
        execution={"exit_code": 0},
    )


class TestPublicationContract(unittest.TestCase):
    def test_base_policy_changed_same_head(self) -> None:
        expected = _context(policy_digest="policy-a")
        current = _context(policy_digest="policy-b")
        decision = validate_publication(_full_report(), expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "stale_policy")
        self.assertEqual(decision.inline_keys, ())

    def test_cross_pr_replay(self) -> None:
        expected = _context(pr_number=1)
        current = _context(pr_number=2)
        decision = validate_publication(_full_report(), expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "cross_pr_replay")

    def test_wrong_workflow_run_artifact(self) -> None:
        expected = _context(run_id="run-1")
        current = _context(run_id="run-2")
        decision = validate_publication(_full_report(), expected, current)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "wrong_workflow_run_artifact")

    def test_missing_or_prefix_head_denied(self) -> None:
        expected = _context(head="deadbeef")
        current = _context(head="deadbeef")
        decision = validate_publication(_full_report(), expected, current)
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
        ctx = _context()
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "deleted_side_location")

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
        ctx = _context()
        decision = validate_publication(report, ctx, ctx)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "limit_failure")
        self.assertEqual(decision.inline_keys, ())

    def test_current_exact_context_authorized(self) -> None:
        ctx = _context()
        decision = validate_publication(_full_report(), ctx, ctx)
        self.assertTrue(decision.authorized)
        self.assertEqual(decision.cause, "authorized")


if __name__ == "__main__":
    unittest.main()
