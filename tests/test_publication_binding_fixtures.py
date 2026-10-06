"""Replay immutable E02 publication-binding fixtures (E02-T2-BIND corpus)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pullraptor.models import Finding, FullReport, LimitFailure, ReviewContract, ScopeEntry, Span
from pullraptor.publication_contract import PublicationContext, scope_digest_from_report, validate_publication

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e02" / "publication-binding"
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


def _scoped_report(receipts: tuple = ()) -> FullReport:
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
    return FullReport(
        schema="1",
        kind="full",
        contract=contract,
        receipts=receipts,
        inventory=("app.py",),
        findings=(),
        diagnostics=(),
        execution={"exit_code": 0},
    )


def _finding(*, side: str = "head", path: str = "app.py") -> Finding:
    return Finding(
        rule="PY001",
        version="1",
        obligation="ob1",
        anchor="a1",
        span=Span(
            path=path,
            side=side,
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


class TestPublicationBindingFixtures(unittest.TestCase):
    def test_manifest_lists_replay_files(self) -> None:
        manifest = json.loads((_FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["scenarios"]:
            self.assertTrue((_FIXTURE_DIR / name).is_file(), msg=name)

    def test_fixture_scenarios_match_validator(self) -> None:
        manifest = json.loads((_FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["scenarios"]:
            with self.subTest(scenario=name):
                raw = json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))
                expect = raw["expect"]
                if raw.get("report_kind") == "limit_failure":
                    report: FullReport | LimitFailure = LimitFailure(
                        schema="1",
                        kind="limit_failure",
                        known_inputs={"head": _HEAD},
                        exit_code=2,
                        analysis_complete=False,
                        details_omitted=True,
                        cause="timeout",
                    )
                    ctx_source = _full_report()
                elif raw.get("use_scoped_contract"):
                    report = _scoped_report(receipts=tuple(raw.get("receipts", ())))
                else:
                    findings: tuple[Finding, ...] = ()
                    if raw.get("finding_side") or raw.get("finding_path"):
                        findings = (
                            _finding(
                                side=str(raw.get("finding_side", "head")),
                                path=str(raw.get("finding_path", "app.py")),
                            ),
                        )
                    report = _full_report(
                        findings=findings,
                        **dict(raw.get("contract_overrides", {})),
                    )
                    if raw.get("contract_overrides"):
                        ctx_source = _full_report()
                    else:
                        ctx_source = report

                if not isinstance(report, LimitFailure):
                    ctx_source = report if not raw.get("contract_overrides") else _full_report()

                expected = _context_for_report(
                    ctx_source if isinstance(ctx_source, FullReport) else _full_report(),
                    **dict(raw.get("expected_context_overrides", {})),
                )
                current = _context_for_report(
                    ctx_source if isinstance(ctx_source, FullReport) else _full_report(),
                    **dict(raw.get("current_context_overrides", {})),
                )
                if raw.get("contract_overrides") and isinstance(report, FullReport):
                    tampered = FullReport(
                        schema=report.schema,
                        kind=report.kind,
                        contract=ReviewContract(
                            base_tip=report.contract.base_tip,
                            comparison_base=report.contract.comparison_base,
                            head=report.contract.head,
                            policy_digest=str(raw["contract_overrides"].get("policy_digest", report.contract.policy_digest)),
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
                    report = tampered

                decision = validate_publication(report, expected, current)
                self.assertEqual(decision.authorized, expect["authorized"])
                self.assertEqual(decision.cause, expect["cause"])
                if "inline_keys" in expect:
                    self.assertEqual(decision.inline_keys, tuple(expect["inline_keys"]))


if __name__ == "__main__":
    unittest.main()
