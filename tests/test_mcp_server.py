"""Unit tests for PullRaptor Model Context Protocol (MCP) server."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
import unittest
from unittest.mock import patch

from pullraptor.__main__ import main
from pullraptor.mcp_server import (
    _DEFAULT_SESSION,
    _tool_definitions,
    _validate_repo_path,
    dispatch_tool,
    process_request,
    run_mcp_server,
)
from tests.helpers import make_repo


class TestMCPServer(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    pass\n"})
        self.repo.commit({"app.py": b"def f():\n    return 42\n"}, message="second")
        self.repo_root = self.repo.root
        self._workspace_patch = patch.dict(
            os.environ,
            {
                "PULLRAPTOR_MCP_WORKSPACE_ROOT": str(self.repo_root.parent),
                "PULLRAPTOR_MCP_REPOSITORY_ID": "test-repo",
            },
        )
        self._workspace_patch.start()
        _DEFAULT_SESSION.reports.clear()
        _DEFAULT_SESSION.active_reviews = 0
        _DEFAULT_SESSION.initialized = False
        _DEFAULT_SESSION.negotiated_version = None
        _DEFAULT_SESSION.report_bytes_total = 0

    def tearDown(self) -> None:
        self._workspace_patch.stop()
        self.repo.cleanup()

    def test_initialize_handshake(self) -> None:
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = process_request(req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(resp["result"]["serverInfo"]["name"], "pullraptor-mcp")

    def test_notification_handling(self) -> None:
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        resp = process_request(notif)
        self.assertIsNone(resp)

    def test_ping(self) -> None:
        req = {"jsonrpc": "2.0", "id": 42, "method": "ping"}
        resp = process_request(req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 42)
        self.assertEqual(resp["result"], {})

    def test_tools_list(self) -> None:
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        resp = process_request(req)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("pullraptor_review", tool_names)
        self.assertIn("pullraptor_get_findings", tool_names)
        self.assertIn("pullraptor_get_coverage", tool_names)
        self.assertIn("pullraptor_explain_finding", tool_names)

    def test_explain_finding_tool(self) -> None:
        result = dispatch_tool("pullraptor_explain_finding", {"rule_id": "PY001"})
        self.assertFalse(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("PY001", text)
        self.assertIn("Default Mutable Parameter", text)
        self.assertIn("Remediation", text)

        # Unknown rule
        unknown = dispatch_tool("pullraptor_explain_finding", {"rule_id": "UNKNOWN99"})
        self.assertFalse(unknown["isError"])
        self.assertIn("No documentation found", unknown["content"][0]["text"])

    def test_unknown_tool(self) -> None:
        result = dispatch_tool("nonexistent_tool", {})
        self.assertTrue(result["isError"])
        self.assertIn("Unknown tool", result["content"][0]["text"])

    def test_path_validation_and_containment(self) -> None:
        valid_path = _validate_repo_path(str(self.repo_root))
        self.assertEqual(valid_path, self.repo_root.resolve())

        with self.assertRaises(ValueError):
            _validate_repo_path("/nonexistent/directory/for/testing")

        workspace = self.repo_root.parent
        outside = workspace.parent
        if outside != workspace:
            with self.assertRaises(ValueError):
                _validate_repo_path(str(outside))

        temp_dir = Path("/tmp")
        if not (temp_dir / ".git").exists():
            with self.assertRaises(ValueError):
                _validate_repo_path(str(temp_dir))

    def _initialize_session(self) -> None:
        init_req = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        process_request(init_req)

    def _review_digest(self) -> str:
        result = dispatch_tool(
            "pullraptor_review",
            {
                "repo_path": str(self.repo_root),
                "base": "HEAD~1",
                "head": "HEAD",
            },
        )
        match = re.search(r"report_digest=([0-9a-f]{64})", result["content"][0]["text"])
        assert match is not None
        return match.group(1)

    def test_review_tool_dispatch(self) -> None:
        self._initialize_session()
        # Review current commit against HEAD~1
        call_req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "pullraptor_review",
                "arguments": {
                    "repo_path": str(self.repo_root),
                    "base": "HEAD~1",
                    "head": "HEAD",
                },
            },
        }
        resp = process_request(call_req)
        self.assertIsNotNone(resp)
        result = resp["result"]
        self.assertFalse(result["isError"])
        self.assertIn("# PullRaptor Review", result["content"][0]["text"])

    def test_get_findings_and_coverage_tools(self) -> None:
        self._initialize_session()
        digest = self._review_digest()
        pin = {"repository_id": "test-repo", "report_digest": digest}
        findings_res = dispatch_tool("pullraptor_get_findings", pin)
        self.assertFalse(findings_res["isError"])
        data = json.loads(findings_res["content"][0]["text"])
        self.assertIn("findings", data)

        # Call get_coverage
        coverage_res = dispatch_tool("pullraptor_get_coverage", pin)
        self.assertFalse(coverage_res["isError"])
        cov_data = json.loads(coverage_res["content"][0]["text"])
        self.assertIn("status", cov_data)
        self.assertIn("receipt_count", cov_data)
        self.assertIn("receipts", cov_data)

    def test_resources_list_and_read(self) -> None:
        self._initialize_session()
        digest = self._review_digest()
        # List resources
        list_req = {"jsonrpc": "2.0", "id": 20, "method": "resources/list"}
        list_resp = process_request(list_req)
        self.assertIsNotNone(list_resp)
        uris = [r["uri"] for r in list_resp["result"]["resources"]]
        self.assertIn("pullraptor://report/latest", uris)
        self.assertIn("pullraptor://coverage/summary", uris)

        # Read resource
        read_req = {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "resources/read",
            "params": {
                "uri": "pullraptor://report/latest",
                "report_digest": digest,
                "repository_id": "test-repo",
            },
        }
        read_resp = process_request(read_req)
        self.assertIsNotNone(read_resp)
        self.assertEqual(read_resp["result"]["contents"][0]["uri"], "pullraptor://report/latest")

    def test_malformed_json_rpc_ignored_gracefully(self) -> None:
        in_stream = io.StringIO("{ not valid json }\n")
        out_stream = io.StringIO()
        code = run_mcp_server(input_stream=in_stream, output_stream=out_stream)
        self.assertEqual(code, 0)
        self.assertEqual(out_stream.getvalue().strip(), "")

    def test_findings_min_severity_filter(self) -> None:
        self._initialize_session()
        digest = self._review_digest()
        pin = {"repository_id": "test-repo", "report_digest": digest}
        all_findings = json.loads(
            dispatch_tool("pullraptor_get_findings", {**pin, "min_severity": "advisory"})["content"][0]["text"]
        )
        high_only = json.loads(
            dispatch_tool("pullraptor_get_findings", {**pin, "min_severity": "error"})["content"][0]["text"]
        )
        self.assertGreaterEqual(all_findings["count"], high_only["count"])

    def test_mcp_event_loop_io(self) -> None:
        input_data = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            )
            + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"})
            + "\n"
        )
        in_stream = io.StringIO(input_data)
        out_stream = io.StringIO()

        code = run_mcp_server(input_stream=in_stream, output_stream=out_stream)
        self.assertEqual(code, 0)

        lines = [line.strip() for line in out_stream.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        resp1 = json.loads(lines[0])
        self.assertEqual(resp1["id"], 1)
        self.assertEqual(resp1["result"]["serverInfo"]["name"], "pullraptor-mcp")
        resp2 = json.loads(lines[1])
        self.assertEqual(resp2["id"], 2)


if __name__ == "__main__":
    unittest.main()
