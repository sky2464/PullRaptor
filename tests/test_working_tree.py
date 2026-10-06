"""Tests for working tree and staged index snapshot freezing (E02A)."""

import io
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

import json

from pullraptor.__main__ import main
from pullraptor.git_snapshot import freeze_working_tree, resolve_inputs
from pullraptor.local_snapshot import LocalReviewRefs, LocalSnapshot, capture_local, resolve_local_review_refs
from pullraptor.mcp_server import _DEFAULT_SESSION, handle_review
from pullraptor.kernel import review
from pullraptor.models import Deadline, Diagnostic, Limits
from tests.helpers import make_repo


class TestWorkingTreeSnapshots(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    pass\n"})
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)
        self._mcp_env = patch.dict(
            os.environ,
            {
                "PULLRAPTOR_DEV_ADMIT_EXTENDED": "1",
                "PULLRAPTOR_MCP_WORKSPACE_ROOT": str(self.repo.root.parent),
                "PULLRAPTOR_MCP_REPOSITORY_ID": "test-repo",
            },
        )
        self._mcp_env.start()
        _DEFAULT_SESSION.active_reviews = 0

    def tearDown(self) -> None:
        _DEFAULT_SESSION.active_reviews = 0
        self._mcp_env.stop()
        self.repo.cleanup()

    def test_staged_snapshot_leaves_index_and_working_tree_untouched(self) -> None:
        app_file = self.repo.root / "app.py"
        app_file.write_text("def f():\n    return 42\n")

        # Stage change
        subprocess.run(["git", "add", "app.py"], cwd=self.repo.root, check=True)

        tree_oid = freeze_working_tree(self.repo.root, self.limits, self.deadline, staged_only=True)
        self.assertEqual(len(tree_oid), 40)

        # Check git status: still staged
        st = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo.root, capture_output=True, text=True, check=True)
        self.assertIn("M  app.py", st.stdout)

        # Review with frozen tree
        report, _, _ = review(
            repo=self.repo.root,
            base_ref="HEAD",
            head_ref=tree_oid,
            is_head_tree=True,
            use_cache=False,
        )
        self.assertEqual(report.kind, "full")
        self.assertEqual(len(report.findings), 0)
        self.assertIn("app.py", report.inventory)

    def test_workdir_snapshot_captures_unstaged_and_untracked_files(self) -> None:
        app_file = self.repo.root / "app.py"
        app_file.write_text("def f():\n    print('dirty')\n")

        untracked_file = self.repo.root / "new_helper.py"
        untracked_file.write_text("def helper():\n    return True\n")

        base_tip, _, _ = resolve_inputs(
            self.repo.root, "HEAD", "HEAD", self.limits, self.deadline, exact_base=True
        )
        snapshot = capture_local(
            self.repo.root,
            base_tip,
            staged_only=False,
            include_untracked=True,
            limits=self.limits,
            deadline=self.deadline,
        )
        tree_oid = snapshot.tree_oid
        self.assertEqual(len(tree_oid), 40)

        # Verify real status still shows unstaged modification and untracked file
        st = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo.root, capture_output=True, text=True, check=True)
        self.assertIn(" M app.py", st.stdout)
        self.assertIn("?? new_helper.py", st.stdout)

        # Review workdir snapshot
        report, _, _ = review(
            repo=self.repo.root,
            base_ref="HEAD",
            head_ref=tree_oid,
            is_head_tree=True,
            use_cache=False,
        )
        self.assertEqual(report.kind, "full")
        self.assertIn("app.py", report.inventory)
        self.assertIn("new_helper.py", report.inventory)

    def test_cli_staged_flag(self) -> None:
        app_file = self.repo.root / "app.py"
        app_file.write_text("def f(x=[]):\n    x.append(1)\n")
        subprocess.run(["git", "add", "app.py"], cwd=self.repo.root, check=True)

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--staged",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        self.assertIn("PY001", out.getvalue())

    def test_cli_workdir_flag(self) -> None:
        app_file = self.repo.root / "app.py"
        app_file.write_text("def f():\n    try:\n        pass\n    except:\n        x = 1\n")

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--workdir",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        self.assertIn("PY002", out.getvalue())

    def test_cli_untracked_default_excluded(self) -> None:
        orphan = self.repo.root / "orphan.py"
        orphan.write_text("def g(x=[]):\n    return x\n")

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--workdir",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertNotIn("orphan.py", payload.get("inventory", []))
        self.assertNotIn("PY001", out.getvalue())

    def test_cli_untracked_explicit_opt_in(self) -> None:
        orphan = self.repo.root / "orphan.py"
        orphan.write_text("def g(x=[]):\n    return x\n")

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--workdir",
                "--include-untracked",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertIn("orphan.py", payload.get("inventory", []))

    def test_mcp_local_snapshot_uses_current_capture(self) -> None:
        captured: dict[str, object] = {}

        def _record_resolve(repo: Path, **kwargs: object) -> LocalReviewRefs:
            captured["kwargs"] = kwargs
            return resolve_local_review_refs(repo, **kwargs)

        with patch("pullraptor.mcp_server.resolve_local_review_refs", side_effect=_record_resolve):
            result = handle_review(
                {
                    "repo_path": str(self.repo.root),
                    "workdir": True,
                    "include_untracked": True,
                }
            )
        self.assertIn("PullRaptor Review", result)
        kwargs = captured["kwargs"]
        self.assertTrue(kwargs["include_untracked"])
        self.assertFalse(kwargs["staged_only"])

    def test_cli_mcp_local_snapshot_canonical_equal(self) -> None:
        app_file = self.repo.root / "app.py"
        app_file.write_text("def f(x=[]):\n    return x\n")

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            cli_code = main([
                "--repo", str(self.repo.root),
                "--workdir",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(cli_code, 0)
        cli_payload = json.loads(out.getvalue())

        mcp_markdown = handle_review({"repo_path": str(self.repo.root), "workdir": True})
        self.assertIn("PullRaptor Review", mcp_markdown)

        local = resolve_local_review_refs(
            self.repo.root,
            staged_only=False,
            include_untracked=False,
            base_ref=None,
            limits=self.limits,
            deadline=self.deadline,
        )
        report, _, _ = review(
            repo=self.repo.root,
            base_ref=local.base_ref,
            head_ref=local.head_ref,
            is_head_tree=True,
            use_cache=False,
        )
        self.assertEqual(sorted(cli_payload.get("inventory", [])), sorted(report.inventory))
        self.assertEqual(cli_payload.get("kind"), report.kind)

    def test_local_partial_receipt_survives_adapter(self) -> None:
        partial = LocalSnapshot(
            tree_oid="",
            base_tip="deadbeef",
            manifest_digest="0" * 64,
            capture_mode="workdir",
            include_untracked=False,
            discovery_complete=False,
            diagnostics=(
                Diagnostic(code="CAPTURE_RACE", message="content changed during capture", cause="capture_race"),
            ),
        )
        blocked = LocalReviewRefs(
            base_ref="HEAD",
            head_ref="",
            is_head_tree=True,
            snapshot=partial,
        )

        err = io.StringIO()
        with patch("pullraptor.__main__.resolve_local_review_refs", return_value=blocked):
            with patch("sys.stdout", io.StringIO()), patch("sys.stderr", err):
                cli_code = main(["--repo", str(self.repo.root), "--workdir"])
        self.assertEqual(cli_code, 2)
        self.assertIn("CAPTURE_RACE", err.getvalue())

        with patch("pullraptor.mcp_server.resolve_local_review_refs", return_value=blocked):
            mcp_payload = json.loads(handle_review({"repo_path": str(self.repo.root), "workdir": True}))
        self.assertEqual(mcp_payload["status"], "capture_incomplete")
        self.assertEqual(mcp_payload["diagnostics"][0]["code"], "CAPTURE_RACE")


if __name__ == "__main__":
    unittest.main()
