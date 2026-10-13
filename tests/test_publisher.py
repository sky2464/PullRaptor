"""Tests for GitHub PR publisher (E02B)."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from pullraptor.publication_contract import PublicationRange, PublicationContext
from pullraptor.publication_transport import TransportResponseLost
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
    # Independently pinned connector fixture; never derive authority from submitted report.
    fixture = Path(__file__).parent / "fixtures/e02/publication-binding/trusted-authority.json"
    base = json.loads(fixture.read_text())
    base["permitted_ranges"] = tuple(PublicationRange(**item) for item in base["permitted_ranges"])
    base.update(overrides)
    return PublicationContext(**base)


def _trusted_current(pr, *, policy_digest="pol1"):
    return replace(_expected_context(), head=pr["head"]["sha"], base_tip=pr["base"]["sha"],
                   policy_digest=policy_digest)


def _publish_trusted(*args, **kwargs):
    submitted = kwargs.get("report_dict", args[0] if args else None)
    kwargs.setdefault("raw_report_bytes", json.dumps(submitted).encode())
    kwargs.setdefault("expected_context", _expected_context())
    policy = kwargs.get("connector", {}).get("policy_digest", "pol1")
    kwargs.setdefault("current_authority", lambda pr: _trusted_current(pr, policy_digest=policy))
    return publish_report(*args, **kwargs)



class TestPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.report_dict = _report_dict()

    @patch("pullraptor.publisher._github_api_request")
    def test_draft_pr_skipped(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload(draft=True))

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = _publish_trusted(
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
            code = _publish_trusted(
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
            code = _publish_trusted(
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
            code = _publish_trusted(
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
        with patch("sys.stderr", err), patch.dict(
            "os.environ",
            {"PULLRAPTOR_DEV_ADMIT_EXTENDED": "1"},
            clear=True,
        ):
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

        _publish_trusted(
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
            code = _publish_trusted(
                report_dict=bad_report,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )

        self.assertEqual(code, 2)
        self.assertTrue("invalid_head" in err.getvalue() or "report_bytes_mismatch" in err.getvalue())
        self.assertEqual(mock_api.call_count, 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_publisher_same_head_policy_scope_drift_zero_writes(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload())
        drift_connector = dict(_CONNECTOR, policy_digest="pol-changed")
        expected = _expected_context(policy_digest="pol1")

        err = io.StringIO()
        with patch("sys.stderr", err):
            code = _publish_trusted(
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
            code = _publish_trusted(
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

        _publish_trusted(
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
    def test_actual_lost_post_response_no_duplicate_write(self, mock_api: MagicMock) -> None:
        reconciled_comment = {
            "id": 501,
            "body": f"{COMMENT_MARKER}\n# PullRaptor Review",
            "user": {"login": "pullraptor-bot"},
        }

        comment_reads = 0

        def side_effect(url: str, token: str, method: str = "GET", payload=None):
            nonlocal comment_reads
            if method == "POST":
                raise TransportResponseLost("response lost after successful POST")
            if method == "GET" and "comments" in url:
                comment_reads += 1
                if comment_reads == 1:
                    return (200, [])
                return (200, [reconciled_comment])
            if "pulls" in url:
                return (200, _pr_payload())
            return (200, {})

        mock_api.side_effect = side_effect
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = _publish_trusted(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )
        self.assertEqual(code, 0)
        self.assertIn("reconciled duplicate delivery", out.getvalue())
        post_calls = [c for c in mock_api.call_args_list if c.kwargs.get("method") == "POST"]
        self.assertEqual(len(post_calls), 1)

    @patch("pullraptor.publisher._github_api_request")
    def test_owned_comment_pagination_bounded(self, mock_api: MagicMock) -> None:
        page1 = [{"id": i, "body": "noise", "user": {"login": "user"}} for i in range(100)]
        page2 = [
            {
                "id": 999,
                "body": f"{COMMENT_MARKER}\nold",
                "user": {"login": "pullraptor-bot"},
            }
        ]
        calls: list[str] = []

        def side_effect(url: str, token: str, method: str = "GET", payload=None):
            calls.append(url)
            if method == "GET" and "comments" in url:
                if "page=1" in url:
                    return (200, page1)
                if "page=2" in url:
                    return (200, page2)
                return (200, [])
            if "pulls" in url:
                return (200, _pr_payload())
            if method == "PATCH":
                return (200, {"id": 999})
            return (200, {})

        mock_api.side_effect = side_effect
        _publish_trusted(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="dummy_token",
            connector=_CONNECTOR,
        )
        self.assertTrue(any("page=1" in u for u in calls))
        self.assertTrue(any("page=2" in u for u in calls))

    @patch("pullraptor.publisher._github_api_request")
    def test_foreign_marker_not_updated_by_publisher(self, mock_api: MagicMock) -> None:
        foreign = {
            "id": 777,
            "body": f"{COMMENT_MARKER}\nforeign",
            "user": {"login": "evil-user"},
        }
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, [foreign]),
            (200, _pr_payload()),
            (201, {"id": 888}),
        ]
        _publish_trusted(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="dummy_token",
            connector=_CONNECTOR,
        )
        methods = [c.kwargs.get("method", "GET") for c in mock_api.call_args_list]
        self.assertNotIn("PATCH", methods)
        patch_targets = [c.args[0] for c in mock_api.call_args_list if c.kwargs.get("method") == "PATCH"]
        self.assertFalse(any("777" in t for t in patch_targets))

    @patch("pullraptor.publisher._github_api_request")
    def test_rate_limit_deferred_receipt(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            (200, _pr_payload()),
            (200, []),
            (200, _pr_payload()),
            RuntimeError("GitHub API HTTP 403 on POST: rate limit exceeded"),
        ]
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = _publish_trusted(
                report_dict=self.report_dict,
                repo_slug="owner/repo",
                pr_number=1,
                token="dummy_token",
                connector=_CONNECTOR,
            )
        self.assertEqual(code, 0)
        self.assertIn("deferred publication", out.getvalue())

    @patch("pullraptor.publisher._github_api_request")
    def test_publication_failure_preserves_report(self, mock_api: MagicMock) -> None:
        mock_api.return_value = (200, _pr_payload(head="f" * 40))
        original = copy.deepcopy(self.report_dict)

        _publish_trusted(
            report_dict=self.report_dict,
            repo_slug="owner/repo",
            pr_number=1,
            token="dummy_token",
            connector=_CONNECTOR,
        )

        self.assertEqual(self.report_dict, original)


if __name__ == "__main__":
    unittest.main()
