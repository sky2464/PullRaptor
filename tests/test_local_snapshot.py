"""Tests for bounded local snapshot capture (E02-A1)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from pullraptor.git_snapshot import resolve_inputs
from pullraptor.local_snapshot import capture_local, resolve_repo_git_dir
from pullraptor.models import Deadline, Diagnostic, Limits
from tests.helpers import make_repo


class TestLocalSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=10.0)

    def _base_tip(self, repo_root: Path) -> str:
        base_tip, _, _ = resolve_inputs(
            repo_root,
            "HEAD",
            "HEAD",
            self.limits,
            self.deadline,
            exact_base=True,
        )
        return base_tip

    def test_filter_sentinel_never_runs(self) -> None:
        repo = make_repo({"tracked.txt": b"hello\n"})
        sentinel = repo.root / ".filter-sentinel"
        filter_script = repo.root / "filter.sh"
        filter_script.write_text(
            "#!/bin/sh\n"
            "touch .filter-sentinel\n"
            "cat\n",
            encoding="utf-8",
        )
        filter_script.chmod(0o755)
        subprocess.run(
            ["git", "config", "filter.sentinel.clean", f"sh {filter_script}"],
            cwd=repo.root,
            check=True,
            capture_output=True,
        )
        (repo.root / ".gitattributes").write_text("tracked.txt filter=sentinel\n", encoding="utf-8")
        tracked = repo.root / "tracked.txt"
        tracked.write_text("mutated\n", encoding="utf-8")

        result = capture_local(
            repo.root,
            self._base_tip(repo.root),
            staged_only=False,
            include_untracked=False,
            limits=self.limits,
            deadline=self.deadline,
        )
        self.assertFalse(sentinel.exists())
        self.assertTrue(result.discovery_complete)
        self.assertEqual(len(result.tree_oid), 40)

        repo.cleanup()

    def test_capture_race_incomplete(self) -> None:
        repo = make_repo({"race.txt": b"stable\n"})
        path = repo.root / "race.txt"

        original = capture_local.__globals__["_read_bounded_file"]

        def racing_read(p: Path, limits: Limits):
            if p.name == "race.txt":
                return (
                    None,
                    Diagnostic(
                        code="CAPTURE_RACE",
                        message="simulated race",
                        path="race.txt",
                        cause="capture_race",
                    ),
                    True,
                )
            return original(p, limits)

        with patch("pullraptor.local_snapshot._read_bounded_file", side_effect=racing_read):
            result = capture_local(
                repo.root,
                self._base_tip(repo.root),
                staged_only=False,
                include_untracked=False,
                limits=self.limits,
                deadline=self.deadline,
            )
        self.assertFalse(result.discovery_complete)
        self.assertTrue(any(d.cause == "capture_race" for d in result.diagnostics))
        repo.cleanup()

    def test_untracked_default_excluded(self) -> None:
        repo = make_repo({"app.py": b"x = 1\n"})
        (repo.root / "new.py").write_text("y = 2\n", encoding="utf-8")
        result = capture_local(
            repo.root,
            self._base_tip(repo.root),
            staged_only=False,
            include_untracked=False,
            limits=self.limits,
            deadline=self.deadline,
        )
        self.assertFalse(result.include_untracked)
        manifest_paths = self._tree_paths(repo.root, result.tree_oid)
        self.assertNotIn("new.py", manifest_paths)
        repo.cleanup()

    def test_untracked_explicit_opt_in(self) -> None:
        repo = make_repo({"app.py": b"x = 1\n"})
        (repo.root / "new.py").write_text("y = 2\n", encoding="utf-8")
        result = capture_local(
            repo.root,
            self._base_tip(repo.root),
            staged_only=False,
            include_untracked=True,
            limits=self.limits,
            deadline=self.deadline,
        )
        manifest_paths = self._tree_paths(repo.root, result.tree_oid)
        self.assertIn("new.py", manifest_paths)
        repo.cleanup()

    def test_worktree_index_and_refs_unchanged(self) -> None:
        repo = make_repo({"app.py": b"def f():\n    pass\n"})
        app = repo.root / "app.py"
        app.write_text("def f():\n    return 1\n", encoding="utf-8")

        index_before = (repo.root / ".git" / "index").read_bytes()
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        capture_local(
            repo.root,
            self._base_tip(repo.root),
            staged_only=False,
            include_untracked=False,
            limits=self.limits,
            deadline=self.deadline,
        )

        index_after = (repo.root / ".git" / "index").read_bytes()
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        self.assertEqual(index_before, index_after)
        self.assertEqual(head_before, head_after)
        self.assertEqual(status_before, status_after)
        repo.cleanup()

    def test_worktree_gitdir_file_supported(self) -> None:
        main_repo = make_repo({"base.py": b"a = 1\n"})
        linked_dir = Path(tempfile.mkdtemp(prefix="pullraptor_wt_"))
        subprocess.run(
            ["git", "worktree", "add", str(linked_dir), "HEAD"],
            cwd=main_repo.root,
            check=True,
            capture_output=True,
        )
        git_file = linked_dir / ".git"
        self.assertTrue(git_file.is_file())

        git_dir = resolve_repo_git_dir(linked_dir, self.deadline, self.limits)
        self.assertTrue(git_dir.exists())

        (linked_dir / "base.py").write_text("a = 2\n", encoding="utf-8")
        result = capture_local(
            linked_dir,
            self._base_tip(linked_dir),
            staged_only=False,
            include_untracked=False,
            limits=self.limits,
            deadline=self.deadline,
        )
        self.assertTrue(result.discovery_complete)
        self.assertEqual(len(result.tree_oid), 40)

        subprocess.run(["git", "worktree", "remove", "--force", str(linked_dir)], cwd=main_repo.root, check=True)
        main_repo.cleanup()

    def _tree_paths(self, repo_root: Path, tree_oid: str) -> set[str]:
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", tree_oid],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return {line for line in res.stdout.splitlines() if line}


if __name__ == "__main__":
    unittest.main()
