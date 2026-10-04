"""Publication trust receipts, isolation admission, and trusted-base CI policy tests."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from pullraptor.publication_trust import (
    AdmissionDecision,
    ArtifactReceipt,
    IsolationControls,
    compare_ci_workflow_policy,
    evaluate_hostile_admission,
    refuse_unavailable_hostile,
    validate_artifact_receipt,
    verify_dev_ci_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "e02" / "ci-controls"


class TestArtifactReceipt(unittest.TestCase):
    def _receipt(self, **overrides: object) -> ArtifactReceipt:
        base = {
            "repository_id": "owner/repo",
            "pr_number": 7,
            "workflow_id": "PullRaptor Review",
            "run_id": "1001",
            "artifact_digest": "a" * 64,
            "reviewer_digest": "b" * 64,
        }
        base.update(overrides)
        return ArtifactReceipt(**base)  # type: ignore[arg-type]

    def test_report_artifact_origin_replay_denied(self) -> None:
        expected = self._receipt()
        replay = self._receipt(run_id="9999")
        decision = validate_artifact_receipt(expected, replay)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.cause, "wrong_workflow_run_artifact")

        cross_pr = self._receipt(pr_number=99)
        decision_pr = validate_artifact_receipt(expected, cross_pr)
        self.assertFalse(decision_pr.authorized)
        self.assertEqual(decision_pr.cause, "cross_pr_replay")

    def test_matching_receipt_authorized(self) -> None:
        receipt = self._receipt()
        decision = validate_artifact_receipt(receipt, receipt)
        self.assertTrue(decision.authorized)


class TestIsolationAdmission(unittest.TestCase):
    def test_actual_egress_filesystem_credential_controls(self) -> None:
        fixture = json.loads((FIXTURES / "hostile-unavailable.json").read_text(encoding="utf-8"))
        controls = IsolationControls(**fixture["controls"])
        decision = evaluate_hostile_admission(controls, profile=fixture["profile"])
        self.assertEqual(decision.admission, "unavailable")
        self.assertIn("egress", decision.cause)

        enforced_fixture = json.loads((FIXTURES / "hostile-enforced.json").read_text(encoding="utf-8"))
        enforced_controls = IsolationControls(**enforced_fixture["controls"])
        enforced = evaluate_hostile_admission(enforced_controls, profile=enforced_fixture["profile"])
        self.assertEqual(enforced.admission, "enforced")

    def test_refuse_unavailable_hostile_exits_nonzero(self) -> None:
        decision = AdmissionDecision(profile="hostile", admission="unavailable", cause="missing_controls:egress")
        self.assertEqual(refuse_unavailable_hostile(decision), 1)

    def test_probe_cli_refuses_without_controls(self) -> None:
        env = os.environ.copy()
        env.pop("PULLRAPTOR_PUBLISH_TOKEN", None)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [os.environ.get("PYTHON", "python3.12"), "-m", "pullraptor.publication_trust", "probe-isolation"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("PULLRAPTOR_ADMISSION=unavailable", result.stdout)


class TestCiWorkflowPolicy(unittest.TestCase):
    def test_head_cannot_elevate_permissions(self) -> None:
        base = "permissions:\n  contents: read\n"
        head = "permissions:\n  contents: write\n"
        violations = compare_ci_workflow_policy(base, head, required_markers=())
        self.assertTrue(any(v.startswith("elevated_permission:contents") for v in violations))

    def test_verify_dev_ci_against_repo(self) -> None:
        base_sha = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        violations = verify_dev_ci_policy(
            repo_root=REPO_ROOT,
            base_revision=base_sha,
            head_path=REPO_ROOT / ".github" / "workflows" / "ci.yml",
            workflow_rel=".github/workflows/ci.yml",
            required_markers=("unittest discover",),
        )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
