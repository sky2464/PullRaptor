"""Tests for PullRaptor safe diff facts and hunk isolation."""

from pathlib import Path
import subprocess
import time
import unittest

from pullraptor.diff import changes
from pullraptor.git_snapshot import read_snapshot
from pullraptor.models import Deadline, Limits
from tests.helpers import make_repo


class TestDiff(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"a.py": b"line 1\nline 2\n"})
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    def tearDown(self) -> None:
        self.repo.cleanup()

    def test_changes_detects_addition_and_modification(self) -> None:
        base_c = self.repo.commit_ids[0]
        base_snap = read_snapshot(self.repo.root, base_c, self.limits, self.deadline)

        head_c = self.repo.commit({"a.py": b"line 1\nline 2 modified\n", "b.py": b"new file\n"})
        head_snap = read_snapshot(self.repo.root, head_c, self.limits, self.deadline)

        diffs = changes(self.repo.root, base_snap, head_snap, self.limits, self.deadline)
        diff_map = {c.path: c for c in diffs}

        self.assertIn("a.py", diff_map)
        self.assertEqual(diff_map["a.py"].kind, "modified")
        self.assertIn("b.py", diff_map)
        self.assertEqual(diff_map["b.py"].kind, "added")

    def test_hostile_external_diff_textconv_fsmonitor_not_executed(self) -> None:
        sentinel_path = self.repo.root / "sentinel.txt"
        if sentinel_path.exists():
            sentinel_path.unlink()

        # Configure hostile external diff in repo git config
        hostile_cmd = f"python3 -c 'from pathlib import Path; Path({str(sentinel_path)!r}).write_text(\"HACKED\")'"
        subprocess.run(["git", "config", "diff.external", hostile_cmd], cwd=self.repo.root, check=True)
        subprocess.run(["git", "config", "diff.textconv", hostile_cmd], cwd=self.repo.root, check=True)
        subprocess.run(["git", "config", "core.fsmonitor", hostile_cmd], cwd=self.repo.root, check=True)

        base_c = self.repo.commit_ids[0]
        base_snap = read_snapshot(self.repo.root, base_c, self.limits, self.deadline)
        head_c = self.repo.commit({"a.py": b"changed\n"})
        head_snap = read_snapshot(self.repo.root, head_c, self.limits, self.deadline)

        # Run changes calculation
        diffs = changes(self.repo.root, base_snap, head_snap, self.limits, self.deadline)
        self.assertTrue(len(diffs) > 0)
        # Sentinel file MUST NOT exist!
        self.assertFalse(sentinel_path.exists())

    def test_attributes_cannot_hide_source(self) -> None:
        # Create .gitattributes saying a.py is binary or -diff
        base_c = self.repo.commit({".gitattributes": b"*.py -diff\n"})
        base_snap = read_snapshot(self.repo.root, base_c, self.limits, self.deadline)

        head_c = self.repo.commit({"a.py": b"line 1\nline 2 changed\n"})
        head_snap = read_snapshot(self.repo.root, head_c, self.limits, self.deadline)

        diffs = changes(self.repo.root, base_snap, head_snap, self.limits, self.deadline)
        diff_a = next(c for c in diffs if c.path == "a.py")
        self.assertEqual(diff_a.kind, "modified")
        self.assertTrue(len(diff_a.hunks) > 0)


if __name__ == "__main__":
    unittest.main()
