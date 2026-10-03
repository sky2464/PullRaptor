"""E08-A1 bounded MCP session and report identity tests."""

from __future__ import annotations

import json
import os
import re
import time
import unittest
from unittest.mock import patch

from pullraptor.mcp_server import _DEFAULT_SESSION, dispatch_tool, handle_message, process_request
from pullraptor.mcp_sessions import (
    MCPSession,
    evict_report,
    get_session_report,
    register_session_report,
    validate_request_bytes,
)
from pullraptor.models import Deadline, FullReport, RecordLimits, ReviewContract
from tests.helpers import make_repo


def _minimal_report() -> FullReport:
    return FullReport(
        schema="1",
        kind="full",
        contract=ReviewContract(
            base_tip="b" * 40,
            comparison_base="c" * 40,
            head="a" * 40,
            policy_digest="p",
            config_digest="cfg",
            tool_digest="tool",
            profile="structural",
            expected_scope=(),
            discovery_complete=True,
        ),
        receipts=(),
        inventory=("app.py",),
        findings=(),
        diagnostics=(),
        execution={"exit_code": 0},
    )


class TestMCPSessions(unittest.TestCase):
    def setUp(self) -> None:
        _DEFAULT_SESSION.reports.clear()
        _DEFAULT_SESSION.active_reviews = 0
        _DEFAULT_SESSION.initialized = False
        _DEFAULT_SESSION.negotiated_version = None
        _DEFAULT_SESSION.report_bytes_total = 0

    def test_cross_repo_session_report_denied(self) -> None:
        session = MCPSession(id="s1", workspace_grants=frozenset({"repo-a"}))
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        pinned = register_session_report(
            session,
            authorized_repository_id="repo-a",
            report=_minimal_report(),
            head_or_snapshot="head-a",
            limits=limits,
            deadline=deadline,
        )
        denied = get_session_report("s1", pinned.report_digest, "repo-b", session=session)
        self.assertIsNone(denied)
        allowed = get_session_report("s1", pinned.report_digest, "repo-a", session=session)
        self.assertIsNotNone(allowed)

    def test_no_implicit_review_on_get(self) -> None:
        session = MCPSession(id="s2", workspace_grants=frozenset())
        session.negotiated_version = "2024-11-05"
        result = dispatch_tool(
            "pullraptor_get_findings",
            {"repository_id": "repo-a", "report_digest": "missing"},
            session=session,
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["status"], "report_not_found")
        self.assertEqual(payload.get("implicit_review_count", 0), 0)

    def test_duplicate_keys_unknown_fields_rejected(self) -> None:
        raw = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","extra":1}}'
        err = validate_request_bytes(raw)
        self.assertIsNone(err)
        resp = handle_message(
            b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","extra":1}}',
            session=MCPSession(id="x", workspace_grants=frozenset()),
        )
        self.assertIsNotNone(resp)
        parsed = json.loads(resp.decode("utf-8"))
        self.assertEqual(parsed["error"]["message"], "unknown_fields")

    def test_oversized_message_bounded(self) -> None:
        huge = b"x" * (1_048_576 + 1)
        self.assertEqual(validate_request_bytes(huge), "oversized_request")

    def test_eviction_explicit(self) -> None:
        session = MCPSession(id="s3", workspace_grants=frozenset())
        limits = RecordLimits()
        deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        pinned = register_session_report(
            session,
            authorized_repository_id="repo-a",
            report=_minimal_report(),
            head_or_snapshot="head",
            limits=limits,
            deadline=deadline,
        )
        self.assertTrue(evict_report(session, pinned.report_digest, limits=limits, deadline=deadline))
        self.assertIsNone(get_session_report("s3", pinned.report_digest, "repo-a", session=session))

    def test_version_negotiation_strict(self) -> None:
        session = MCPSession(id="s4", workspace_grants=frozenset())
        resp = process_request(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "initialize",
                "params": {"protocolVersion": "2099-01-01"},
            },
            session=session,
        )
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["message"], "version_unsupported")


class TestMCPSessionReviewFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    pass\n"})
        self.repo.commit({"app.py": b"def f():\n    return 1\n"}, message="second")
        self.repo_root = self.repo.root
        self._workspace_patch = patch.dict(
            os.environ,
            {
                "PULLRAPTOR_MCP_WORKSPACE_ROOT": str(self.repo_root.parent),
                "PULLRAPTOR_MCP_REPOSITORY_ID": "repo-a",
            },
        )
        self._workspace_patch.start()
        _DEFAULT_SESSION.reports.clear()
        _DEFAULT_SESSION.negotiated_version = "2024-11-05"

    def tearDown(self) -> None:
        self._workspace_patch.stop()
        self.repo.cleanup()

    def test_review_then_get_findings_by_digest(self) -> None:
        review = dispatch_tool(
            "pullraptor_review",
            {"repo_path": str(self.repo_root), "base": "HEAD~1", "head": "HEAD"},
        )
        digest_match = re.search(r"report_digest=([0-9a-f]{64})", review["content"][0]["text"])
        self.assertIsNotNone(digest_match)
        digest = digest_match.group(1)
        findings = dispatch_tool(
            "pullraptor_get_findings",
            {"repository_id": "repo-a", "report_digest": digest},
        )
        data = json.loads(findings["content"][0]["text"])
        self.assertIn("findings", data)
        self.assertNotEqual(data.get("status"), "report_not_found")


if __name__ == "__main__":
    unittest.main()
