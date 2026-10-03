"""Tests for GitHub PR publisher (E02B)."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from pullraptor.publisher import COMMENT_MARKER, main, publish_report


class TestPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.report_dict = {
            "schema": "1",
            "kind": "full",
            "contract": {
                "base_tip": "base_commit_123",
                "comparison_base": "base_commit_123",
                "head": "head_commit_456",
                "policy_digest": "pol1",
                "config_digest": "cfg1",
                "tool_digest": "tool1",
                "profile": "structural",
                "expected_scope": [],
                "discovery_complete": True,
            },
            "receipts": [],
            "inventory": ["app.py"],
            "exclusions": [],
            "findings": [],
            "diagnostics": [],
            "execution": {"exit_code": 0},
        }

    @patch("pullraptor.publisher._github_api_request")
    def test_draft_pr_skipped(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, {"head": {"sha": "head_commit_456"}, "draft": True})

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                publish_draft=False,
            )

        self.assertEqual(code, 0)
        self.assertIn("draft; skipping", out.getvalue())
        # Only 1 API call (fetch PR) made, no comment posted
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_head_drift_rejected_with_exit_2(self, mock_api: MagicMock) -> None:
        # PR head is now newer than reviewed head
        mock_api.return_value = (200, {"head": {"sha": "newer_commit_789"}, "draft": False})

        err = io.StringIO()
        with patch("sys.stderr", err):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
            )

        self.assertEqual(code, 2)
        self.assertIn("STALE_PR_HEAD", err.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_publish_new_comment(self, mock_api: MagicMock) -> None:
        # 1: fetch PR, 2: fetch comments (empty), 3: post comment
        mock_api.side_effect = [
            (200, {"head": {"sha": "head_commit_456"}, "draft": False}),
            (200, []),
            (201, {"id": 101}),
        ]

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
            )

        self.assertEqual(code, 0)
        self.assertIn("Published review comment 101", out.getvalue())
        self.assertEqual(mock_api.call_count, 3)

        # Check comment payload contained marker
        call_post = mock_api.call_args_list[2]
        payload = call_post.kwargs["payload"]
        self.assertIn(COMMENT_MARKER, payload["body"])

    @patch("pullraptor.publisher._github_api_request")
    def test_update_existing_comment_idempotency(self, mock_api: MagicMock) -> None:
        existing_comment = {
            "id": 999,
            "body": f"{COMMENT_MARKER}\nOld review text",
        }
        mock_api.side_effect = [
            (200, {"head": {"sha": "head_commit_456"}, "draft": False}),
            (200, [existing_comment]),
            (200, {"id": 999}),
        ]

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = publish_report(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
            )

        self.assertEqual(code, 0)
        self.assertIn("Updated existing review comment 999", out.getvalue())
        self.assertEqual(mock_api.call_count, 3)

        # Verify PATCH method on existing comment ID
        call_patch = mock_api.call_args_list[2]
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


if __name__ == "__main__":
    unittest.main()
