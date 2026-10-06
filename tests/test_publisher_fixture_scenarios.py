"""Replay E02-T2-INTEGRATE publisher fixture scenarios (mocked GitHub API)."""

from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pullraptor.publisher import report_from_decoded
from tests.test_publisher import _publish_trusted, _expected_context

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e02" / "publisher"
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


def _limit_failure_dict() -> dict:
    return {
        "schema": "1",
        "kind": "limit_failure",
        "known_inputs": {"head": _HEAD},
        "exit_code": 2,
        "analysis_complete": False,
        "details_omitted": True,
        "cause": "timeout",
    }


def _pr_payload(head: str = _HEAD, *, draft: bool = False) -> dict:
    return {"head": {"sha": head}, "base": {"sha": _BASE}, "draft": draft}


class TestPublisherFixtureScenarios(unittest.TestCase):
    def test_manifest_lists_scenarios(self) -> None:
        manifest = json.loads((_FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["scenarios"]:
            self.assertTrue((_FIXTURE_DIR / name).is_file(), msg=name)

    @patch("pullraptor.publisher._github_api_request")
    def test_fixture_scenarios(self, mock_api: MagicMock) -> None:
        manifest = json.loads((_FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["scenarios"]:
            with self.subTest(scenario=name):
                raw = json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))
                if raw.get("report_kind") == "limit_failure":
                    report = _limit_failure_dict()
                else:
                    report = _report_dict()

                if raw.get("policy_drift"):
                    mock_api.return_value = (200, _pr_payload())
                    connector = dict(_CONNECTOR, policy_digest="pol-changed")
                    pinned = _expected_context()
                else:
                    mock_api.return_value = (200, _pr_payload())
                    connector = dict(_CONNECTOR)
                    pinned = None

                if raw.get("head_mismatch"):
                    mock_api.return_value = (200, _pr_payload(head="d" * 40))
                    connector = dict(_CONNECTOR)
                    pinned = None

                mock_api.reset_mock()
                stderr = io.StringIO()
                stdout = io.StringIO()
                kwargs = {
                    "report_dict": report,
                    "repo_slug": "owner/repo",
                    "pr_number": 1,
                    "token": "token",
                    "connector": connector,
                    "preview_only": bool(raw.get("preview_only")),
                }
                if pinned is not None:
                    kwargs["expected_context"] = pinned
                if raw.get("markdown_override"):
                    kwargs["markdown_override"] = str(raw["markdown_override"])

                with patch("sys.stderr", stderr), patch("sys.stdout", stdout):
                    code = _publish_trusted(**kwargs)

                self.assertEqual(code, raw["expect_exit"])
                if "expect_cause_substring" in raw:
                    self.assertIn(raw["expect_cause_substring"], stderr.getvalue())
                if "expect_stderr_substring" in raw:
                    self.assertIn(raw["expect_stderr_substring"], stderr.getvalue())
                if raw.get("expect_override_stderr"):
                    self.assertIn("override ignored", stderr.getvalue())
                if "expect_api_calls_max" in raw:
                    self.assertLessEqual(mock_api.call_count, raw["expect_api_calls_max"])


if __name__ == "__main__":
    unittest.main()
