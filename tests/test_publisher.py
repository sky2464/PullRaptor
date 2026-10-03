"""Tests for GitHub PR publisher (E02B)."""

from __future__ import annotations

import copy
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from pullraptor.publication_contract import PublicationContext, scope_digest_from_report
from pullraptor.publisher import COMMENT_MARKER, main, publish_report, report_from_decoded

_HEAD = "a" * 40
_BASE = "b" * 40
_COMP = "c" * 40

_CONNECTOR = {
    "workflow_id": "wf-1",
    "run_id": "run-1",
    "artifact_digest": "art-1",
    "reviewer_digest": "rev-1",
    "policy_digest": "pol1",
}


def _report_dict(**contract_overrides: object) -> dict:
    contract = {
        "base_tip": _BASE,
        "comparison_base": _COMP,
        "head": _HEAD,
        "policy_digest": "pol1",
        "config_digest": "cfg1",
        "tool_digest": "tool1",
        "profile": "structural",
        "expected_scope": [],
        "discovery_complete": True,
    }
    contract.update(contract_overrides)
    return {
        "schema": "1",
        "kind": "full",
        "contract": contract,
        "receipts": [],
        "inventory": ["app.py"],
        "exclusions": [],
        "findings": [],
        "diagnostics": [],
        "execution": {"exit_code": 0},
    }


def _pr_payload(head: str = _HEAD, *, draft: bool = False) -> dict:
    return {"head": {"sha": head}, "base": {"sha": _BASE}, "draft": draft}


def _expected_context(**overrides: object) -> PublicationContext:
    report = report_from_decoded(_report_dict())
    assert hasattr(report, "contract")
    base = {
        "repository_id": "owner/repo",
        "pr_number": 1,
        "workflow_id": _CONNECTOR["workflow_id"],
        "run_id": _CONNECTOR["run_id"],
        "artifact_digest": _CONNECTOR["artifact_digest"],
        "reviewer_digest": _CONNECTOR["reviewer_digest"],
        "head": _HEAD,
        "base_tip": _BASE,
        "comparison_base": _COMP,
        "policy_digest": "pol1",
        "scope_digest": scope_digest_from_report(report),
    }
    base.update(overrides)
    return PublicationContext(**base)


class TestPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.report_dict = _report_dict()

    @patch("pullraptor.publisher._github_api_request")
    def test_draft_pr_skipped(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload(draft=True))

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                publish_draft=False,
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 0)
        self.assertIn("draft; skipping", out.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_head_drift_rejected_with_exit_2(self, mock_api: MagicMock) -> None:
        newer = "d" * 40
        mock_api.return_value = (200, _pr_payload(head=newer))

        err = io.StringIO()
        with patch("sys.stderr", err):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 2)
        self.assertIn("stale_head", err.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_publish_new_comment(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, []),
            (200, _pr_payload()),
            (201, {"id": 101}),
        ]

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 0)
        self.assertIn("Published review comment 101", out.getvalue())
        self.assertEqual(mock_api.call_count, 4)

        call_post = mock_api.call_args_list[3]
        payload = call_post.kwargs["payload"]
        self.assertIn(COMMENT_MARKER, payload["body"])
        self.assertIn("# PullRaptor Review", payload["body"])

    @patch("pullraptor.publisher._github_api_request")
    def test_update_existing_comment_idempotency(self, mock_api: MagicMock) -> None:
        existing_comment = {
            "id": 999,
            "body": f"{COMMENT_MARKER}\nOld review text",
            "user": {"login": "pullraptor-bot"},
        }
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, [existing_comment]),
            (200, _pr_payload()),
            (200, {"id": 999}),
        ]

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 0)
        self.assertIn("Updated existing review comment 999", out.getvalue())
        self.assertEqual(mock_api.call_count, 4)

        call_patch = mock_api.call_args_list[3]
        self.assertEqual(call_patch.kwargs["method"], "PATCH")
        self.assertIn("comments/999", call_patch.args[0])

    def test_cli_missing_token_error(self) -> None:
        err = io.StringIO()
        with patch("sys.stderr", err), patch.dict("os.environ", {}, clear=True):
            code = main([
                "--report", "-",
                "--repo-slug", "owner/repo",
                "--pr", "1",
                "--token-env", "NONEXISTENT_TOKEN",
            ])
        self.assertEqual(code, 3)
        self.assertIn("Missing GitHub token", err.getvalue())

    @patch("pullraptor.publisher.validate_publication")
    @patch("pullraptor.publisher._github_api_request")
    def test_publisher_calls_binding_gate(
        self,
        mock_api: MagicMock,
        mock_validate: MagicMock,
    ) -> None:
        from pullraptor.publication_contract import PublicationDecision

        mock_validate.return_value = PublicationDecision(
            authorized=True,
            cause="authorized",
            inline_keys=(),
        )
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, []),
            (200, _pr_payload()),
            (201, {"id": 1}),
        ]

        publish_report(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="token",
            connector=_CONNECTOR,
        )

        self.assertGreaterEqual(mock_validate.call_count, 2)

    @patch("pullraptor.publisher._github_api_request")
    def test_publisher_missing_prefix_head_zero_writes(self, mock_api: MagicMock) -> None:
        bad_report = _report_dict(head="head_commit_456")
        mock_api.return_value = (200, _pr_payload(head="head_commit_4567890123456789012345678901234567890"))

        err = io.StringIO()
        with patch("sys.stderr", err):
            code = publish_report(
                report_dict=bad_report,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 2)
        self.assertIn("invalid_head", err.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_publisher_same_head_policy_scope_drift_zero_writes(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload())
        drift_connector = dict(_CONNECTOR, policy_digest="pol-changed")
        expected = _expected_context(policy_digest="pol1")

        err = io.StringIO()
        with patch("sys.stderr", err):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=drift_connector,
                expected_context=expected,
            )

        self.assertEqual(code, 2)
        self.assertIn("stale_policy", err.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_publish_preview_zero_writes(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload())

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
                preview_only=True,
            )

        self.assertEqual(code, 0)
        self.assertIn("preview only", out.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_untrusted_override_cannot_bypass_rendering(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, []),
            (200, _pr_payload()),
            (201, {"id": 55}),
        ]
        evil = "<script>alert('x')</script>"

        publish_report(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="dummy_token",
            connector=_CONNECTOR,
            markdown_override=evil,
        )

        payload = mock_api.call_args_list[3].kwargs["payload"]
        self.assertNotIn("<script>", payload["body"])
        self.assertIn("# PullRaptor Review", payload["body"])

    @patch("pullraptor.publisher._github_api_request")
    def test_publication_failure_preserves_report(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload(head="f" * 40))
        original = copy.deepcopy(self.report_dict)

        publish_report(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="dummy_token",
            connector=_CONNECTOR,
        )

        self.assertEqual(self.report_dict, original)


if __name__ == "__main__":
    unittest.main()
