"""Tests for PullRaptor CLI interface."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pullraptor.__main__ import main
from tests.helpers import make_repo


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    pass\n"})

    def tearDown(self) -> None:
        self.repo.cleanup()

    def test_cli_help(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_structural_python_complete(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def f():\n    print(1)\n"})

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--base", base_c,
                "--head", head_c,
                "--exact-base",
                "--format", "markdown",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        self.assertIn("PullRaptor Review", out.getvalue())

    def test_explicit_diff_profile_scope_statement(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def f():\n    print(2)\n"})

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--base", base_c,
                "--head", head_c,
                "--exact-base",
                "--profile", "diff",
                "--format", "json",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        self.assertIn('"profile":"diff"', out.getvalue())

    def test_stdout_machine_format_stderr_diagnostics(self) -> None:
        base_c = self.repo.commit_ids[0]
        head_c = self.repo.commit({"app.py": b"def f():\n    # changed\n    pass\n"})

        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = main([
                "--repo", str(self.repo.root),
                "--base", base_c,
                "--head", head_c,
                "--exact-base",
                "--format", "sarif",
                "--no-cache",
            ])
        self.assertEqual(code, 0)
        import json
        data = json.loads(out.getvalue())
        self.assertEqual(data["version"], "2.1.0")


if __name__ == "__main__":
    unittest.main()
