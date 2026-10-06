"""Beta 0.1.x excluded entrypoint containment (BR-08; not independent acceptance)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestBetaEntrypoints(unittest.TestCase):
    def _run_module(self, module: str, argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        if env is None or "PULLRAPTOR_DEV_ADMIT_EXTENDED" not in env:
            merged.pop("PULLRAPTOR_DEV_ADMIT_EXTENDED", None)
        return subprocess.run(
            [sys.executable, "-m", module, *argv],
            cwd=REPO_ROOT,
            env={**merged, "PYTHONPATH": str(REPO_ROOT / "src")},
            capture_output=True,
            text=True,
        )

    def test_publish_help_refuses_without_dev_override(self) -> None:
        proc = self._run_module("pullraptor.publisher", ["--help"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pullraptor-publish", proc.stderr)

    def test_publish_script_refuses_without_dev_override(self) -> None:
        proc = self._run_module(
            "pullraptor.publisher",
            ["--report", "-", "--repo-slug", "o/r", "--pr", "1"],
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("excludes console script", proc.stderr)
        self.assertIn("pullraptor-publish", proc.stderr)

    def test_mcp_script_refuses_without_dev_override(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pullraptor.mcp_server import console_main; raise SystemExit(console_main())",
            ],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pullraptor-mcp", proc.stderr)

    def test_cli_mcp_flag_refuses(self) -> None:
        proc = self._run_module("pullraptor.__main__", ["--mcp"])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("excludes MCP", proc.stderr)

    def test_cli_staged_refuses(self) -> None:
        proc = self._run_module("pullraptor.__main__", ["--staged", "--repo", "."])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("local snapshot", proc.stderr.lower())

    def test_dev_override_allows_publish_parse_path(self) -> None:
        proc = self._run_module(
            "pullraptor.publisher",
            ["--report", "-", "--repo-slug", "o/r", "--pr", "1"],
            env={"PULLRAPTOR_DEV_ADMIT_EXTENDED": "1", "GITHUB_TOKEN": ""},
        )
        self.assertNotEqual(proc.returncode, 2)
        self.assertNotIn("excludes console script", proc.stderr)


if __name__ == "__main__":
    unittest.main()
