"""Tests for publication lifecycle reconciliation (E02-A3)."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from pullraptor.models import Finding, FullReport, LimitFailure, ReviewContract, Span
from pullraptor.publication_contract import PublicationContext
from pullraptor.publication_lifecycle import (
    INLINE_CAP,
    InertPublicationConnector,
    PublishedObservation,
    plan_publication,
    revision_observation_id,
    stable_obligation_key,
)

_HEAD = "a" * 40
_BASE = "b" * 40
_COMP = "c" * 40
_OWNER = "pullraptor-bot"
_FIXTURE = Path(__file__).parent / "fixtures" / "e02" / "lifecycle" / "identity-cases.json"


def _witness(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context(**overrides: object) -> PublicationContext:
    values: dict[str, object] = {
        "repository_id": "acme/app",
        "pr_number": 7,
        "workflow_id": "review",
        "run_id": "1",
        "artifact_digest": "ab" * 32,
        "reviewer_digest": "cd" * 32,
        "head": _HEAD,
        "base_tip": _BASE,
        "comparison_base": _COMP,
        "policy_digest": "policy",
        "scope_digest": "11" * 32,
    }
    values.update(overrides)
    return PublicationContext(**values)  # type: ignore[arg-type]


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


def _finding(
    rule: str = "PY001",
    witness: str = "w",
    anchor: str = "a1",
    *,
    version: str = "1",
    obligation: str | None = None,
    path: str = "app.py",
) -> Finding:
    return Finding(
        rule=rule,
        version=version,
        obligation=rule if obligation is None else obligation,
        anchor=anchor,
        span=Span(
            path=path,
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


def _owned(
    finding: Finding,
    *,
    context: PublicationContext | None = None,
    observation_id: str = "obs-1",
    platform_id: str = "gh-1",
    owner_id: str = _OWNER,
    witness: str | None = None,
    witness_digest: str | None = None,
    dismissed: bool = False,
) -> PublishedObservation:
    pinned = _context() if context is None else context
    digest = witness_digest
    if digest is None:
        digest = _witness(finding.witness if witness is None else witness)
    return PublishedObservation(
        owner_id=owner_id,
        platform_id=platform_id,
        obligation_key=stable_obligation_key(pinned, finding),
        observation_id=observation_id,
        witness_digest=digest,
        dismissed=dismissed,
    )


def _plan(report, existing, **kwargs):
    context = kwargs.pop("context", _context())
    owner = kwargs.pop("proven_owner_id", _OWNER)
    return plan_publication(context, report, existing, proven_owner_id=owner)


class TestPublicationLifecycle(unittest.TestCase):
    def test_duplicate_delivery_no_second_comment(self) -> None:
        finding = _finding(witness="w")
        plan = _plan(_report((finding,)), (_owned(finding),))
        self.assertEqual(plan.create, ())
        self.assertEqual(plan.update, ())

    def test_post_timeout_reconcile_owner(self) -> None:
        finding = _finding(witness="w")
        existing = (
            _owned(finding, platform_id="gh-99", observation_id="obs-timeout"),
        )
        plan = _plan(_report((finding,)), existing)
        self.assertEqual(plan.create, ())
        self.assertEqual(plan.update, ())

    def test_foreign_marker_not_updated(self) -> None:
        finding = _finding()
        foreign_comment_id = "foreign-55"
        existing = (
            _owned(
                finding,
                owner_id="other-user",
                platform_id=foreign_comment_id,
                observation_id=foreign_comment_id,
                witness_digest="x",
            ),
        )
        plan = _plan(_report((finding,)), existing)
        self.assertNotIn(foreign_comment_id, plan.update)
        self.assertEqual(plan.create, (stable_obligation_key(_context(), finding),))

    def test_changed_witness_renews_review(self) -> None:
        finding = _finding(witness="new")
        existing = (
            _owned(finding, observation_id="obs-renew", witness="old"),
        )
        plan = _plan(_report((finding,)), existing)
        self.assertIn("obs-renew", plan.update)
        self.assertEqual(plan.renewed[0][0], "obs-renew")
        self.assertNotEqual(plan.renewed[0][1], "obs-renew")
        self.assertNotEqual(plan.renewed[0][1], stable_obligation_key(_context(), finding))

    def test_dismissal_not_resolution(self) -> None:
        finding = _finding(witness="w")
        report = _report((finding,))
        existing = (
            _owned(finding, observation_id="obs-dismissed", dismissed=True),
        )
        plan = _plan(report, existing)
        self.assertIn(stable_obligation_key(_context(), finding), plan.deferred)
        self.assertNotIn("obs-dismissed", plan.update)
        self.assertNotIn("obs-dismissed", plan.outdated)
        self.assertEqual(report.findings, (finding,))

    def test_ten_inline_cap_full_summary(self) -> None:
        findings = tuple(_finding(rule=f"R{i:02d}", anchor=f"a{i}") for i in range(12))
        plan = _plan(_report(findings), ())
        self.assertEqual(len(plan.create), INLINE_CAP)
        self.assertEqual(len(plan.deferred), 2)
        self.assertEqual(plan.out_of_cap, plan.deferred)
        self.assertEqual(len(findings), 12)

    def test_rule_path_version_key_collision_visible(self) -> None:
        fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        context = _context(
            repository_id=fixture["repository_id"],
            pr_number=fixture["pr_number"],
        )
        findings = tuple(
            _finding(
                item["rule"],
                item["witness"],
                item["anchor"],
                version=item["version"],
                obligation=item["obligation"],
                path=item["path"],
            )
            for item in fixture["rule_path_version_collision"]
        )
        plan = _plan(_report(findings), (), context=context)
        keys = tuple(stable_obligation_key(context, finding) for finding in findings)
        self.assertEqual(len(set(keys)), len(keys))
        self.assertEqual(plan.create, keys)
        self.assertEqual(plan.ambiguous, ())
        other_pr = stable_obligation_key(replace(context, pr_number=8), findings[0])
        self.assertNotEqual(keys[0], other_pr)
        moved_head = replace(context, head="d" * 40)
        self.assertEqual(keys[0], stable_obligation_key(moved_head, findings[0]))
        first = revision_observation_id(
            obligation_key=keys[0],
            head=context.head,
            witness_digest=_witness(findings[0].witness),
        )
        second = revision_observation_id(
            obligation_key=keys[0],
            head=moved_head.head,
            witness_digest=_witness(findings[0].witness),
        )
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, keys[0])

    def test_beyond_cap_existing_observation_not_falsely_outdated(self) -> None:
        fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        count = fixture["beyond_cap_count"]
        self.assertGreater(count, INLINE_CAP)
        findings = tuple(_finding(rule=f"R{i:02d}", anchor=f"a{i}") for i in range(count))
        beyond = findings[INLINE_CAP]
        observation_id = fixture["beyond_cap_observation_id"]
        existing = (_owned(beyond, observation_id=observation_id),)
        plan = _plan(_report(findings), existing)
        self.assertNotIn(observation_id, plan.outdated)
        self.assertNotIn(observation_id, plan.update)
        key = stable_obligation_key(_context(), beyond)
        self.assertIn(key, plan.out_of_cap)
        self.assertIn(key, plan.deferred)
        self.assertEqual(len(plan.create), INLINE_CAP)

    def test_duplicate_existing_keys_stay_visible(self) -> None:
        finding = _finding()
        first = _owned(finding, observation_id="obs-a", platform_id="p1")
        second = _owned(finding, observation_id="obs-b", platform_id="p2")
        orders = ((first, second), (second, first))
        plans = [_plan(_report((finding,)), order) for order in orders]
        for plan in plans:
            self.assertEqual(plan.create, ())
            self.assertEqual(plan.update, ())
            self.assertEqual(plan.outdated, ())
            self.assertEqual(plan.ambiguous, (stable_obligation_key(_context(), finding),))
        self.assertEqual(plans[0].ambiguous, plans[1].ambiguous)
        connector = InertPublicationConnector(_context(), orders[0], _OWNER)
        self.assertEqual(connector.write_observation(plans[0]), "ambiguous_observation_match")
        self.assertEqual(connector.write_receipts, ["ambiguous_observation_match"])
        self.assertEqual(connector.list_owned_observations(), orders[0])

    def test_changed_witness_after_dismissal_renews_same_observation(self) -> None:
        finding = _finding(witness="new")
        existing = (
            _owned(finding, observation_id="obs-dismissed", witness="old", dismissed=True),
        )
        plan = _plan(_report((finding,)), existing)
        self.assertEqual(plan.update, ("obs-dismissed",))
        self.assertEqual(plan.renewed[0][0], "obs-dismissed")
        self.assertNotIn(stable_obligation_key(_context(), finding), plan.deferred)
        self.assertNotIn("obs-dismissed", plan.outdated)

    def test_partial_report_does_not_drop_findings(self) -> None:
        finding = _finding()
        existing = (_owned(finding, observation_id="obs-kept"),)
        partial = LimitFailure(
            schema="1",
            kind="limit_failure",
            known_inputs={"head": _HEAD},
            exit_code=2,
            analysis_complete=False,
            details_omitted=True,
            cause="deadline",
        )
        plan = _plan(partial, existing)
        self.assertEqual(plan, _empty_like())
        self.assertNotIn("obs-kept", plan.outdated)

    def test_unproved_owner_plans_no_write(self) -> None:
        finding = _finding()
        existing = (_owned(finding, observation_id="obs-owned"),)
        plan = _plan(_report((finding,)), existing, proven_owner_id="")
        self.assertEqual(plan.create, ())
        self.assertEqual(plan.update, ())
        self.assertEqual(plan.outdated, ())
        self.assertIn(stable_obligation_key(_context(), finding), plan.deferred)
        connector = InertPublicationConnector(_context(), existing, "")
        self.assertEqual(connector.list_owned_observations(), ())

    def test_foreign_owner_is_not_listed_as_owned(self) -> None:
        finding = _finding()
        foreign = _owned(finding, owner_id="other-user", observation_id="foreign-55")
        connector = InertPublicationConnector(_context(), (foreign,), _OWNER)
        self.assertEqual(connector.list_owned_observations(), ())


def _empty_like():
    from pullraptor.publication_lifecycle import PublicationPlan

    return PublicationPlan(create=(), update=(), outdated=(), deferred=())


if __name__ == "__main__":
    unittest.main()
