"""Tests for working tree and staged index snapshot freezing (E02A)."""

import io
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

from pullraptor.__main__ import main
from pullraptor.git_snapshot import freeze_working_tree, resolve_inputs
from pullraptor.kernel import review
from pullraptor.models import Deadline, Limits
from tests.helpers import make_repo


class TestWorkingTreeSnapshots(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    pass\n"})
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)

    def tearDown(self) -> None:
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

        tree_oid = freeze_working_tree(self.repo.root, self.limits, self.deadline, staged_only=False)
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


if __name__ == "__main__":
    unittest.main()
