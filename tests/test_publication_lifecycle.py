"""Tests for publication lifecycle reconciliation (E02-A3)."""

from __future__ import annotations

import hashlib
import unittest

from pullraptor.models import Finding, FullReport, ReviewContract, Span
from pullraptor.publication_lifecycle import PublishedObservation, plan_publication

_HEAD = "a" * 40
_BASE = "b" * 40
_COMP = "c" * 40


def _report(findings: tuple[Finding, ...]) -> FullReport:
    return FullReport(
        schema="1",
        kind="full",
        contract=ReviewContract(
            base_tip=_BASE,
            comparison_base=_COMP,
            head=_HEAD,
            policy_digest="p",
            config_digest="c",
            tool_digest="t",
            profile="structural",
            expected_scope=(),
            discovery_complete=True,
        ),
        receipts=(),
        inventory=("app.py",),
        findings=findings,
        diagnostics=(),
        execution={"exit_code": 0},
    )


def _finding(rule: str = "PY001", witness: str = "w", anchor: str = "a1") -> Finding:
    return Finding(
        rule=rule,
        version="1",
        obligation=rule,
        anchor=anchor,
        span=Span(
            path="app.py",
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
        witness=witness,
    )


class TestPublicationLifecycle(unittest.TestCase):
    def test_duplicate_delivery_no_second_comment(self) -> None:
        witness = hashlib.sha256(b"w").hexdigest()
        existing = (
            PublishedObservation(
                owner_id="pullraptor-bot",
                platform_id="gh-1",
                obligation_key="PY001:a1",
                observation_id="obs-1",
                witness_digest=witness,
                dismissed=False,
            ),
        )
        plan = plan_publication("art-1", _report((_finding(witness="w"),)), existing)
        self.assertEqual(plan.create, ())

    def test_post_timeout_reconcile_owner(self) -> None:
        witness = hashlib.sha256(b"w").hexdigest()
        existing = (
            PublishedObservation(
                owner_id="pullraptor-bot",
                platform_id="gh-99",
                obligation_key="PY001:a1",
                observation_id="obs-timeout",
                witness_digest=witness,
                dismissed=False,
            ),
        )
        plan = plan_publication("art-1", _report((_finding(witness="w"),)), existing)
        self.assertEqual(plan.create, ())

    def test_foreign_marker_not_updated(self) -> None:
        foreign_comment_id = "foreign-55"
        existing = (
            PublishedObservation(
                owner_id="other-user",
                platform_id=foreign_comment_id,
                obligation_key="PY001:a1",
                observation_id=foreign_comment_id,
                witness_digest="x",
                dismissed=False,
            ),
        )
        plan = plan_publication("art-1", _report((_finding(),)), existing)
        self.assertNotIn(foreign_comment_id, plan.update)

    def test_changed_witness_renews_review(self) -> None:
        old = hashlib.sha256(b"old").hexdigest()
        existing = (
            PublishedObservation(
                owner_id="pullraptor-bot",
                platform_id="gh-1",
                obligation_key="PY001:a1",
                observation_id="obs-renew",
                witness_digest=old,
                dismissed=False,
            ),
        )
        plan = plan_publication("art-1", _report((_finding(witness="new"),)), existing)
        self.assertIn("obs-renew", plan.update)

    def test_dismissal_not_resolution(self) -> None:
        witness = hashlib.sha256(b"w").hexdigest()
        existing = (
            PublishedObservation(
                owner_id="pullraptor-bot",
                platform_id="gh-1",
                obligation_key="PY001:a1",
                observation_id="obs-dismissed",
                witness_digest=witness,
                dismissed=True,
            ),
        )
        plan = plan_publication("art-1", _report((_finding(witness="w"),)), existing)
        self.assertIn("PY001:a1", plan.deferred)
        self.assertNotIn("obs-dismissed", plan.update)

    def test_ten_inline_cap_full_summary(self) -> None:
        findings = tuple(_finding(rule=f"R{i:02d}", anchor=f"a{i}") for i in range(12))
        plan = plan_publication("art-1", _report(findings), ())
        self.assertEqual(len(plan.create), 10)
        self.assertEqual(len(plan.deferred), 2)


if __name__ == "__main__":
    unittest.main()
