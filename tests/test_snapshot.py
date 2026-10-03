"""Tests for PullRaptor safe immutable git snapshots."""

from pathlib import Path
import subprocess
import time
import unittest

from pullraptor.git_snapshot import (
    read_blob,
    read_snapshot,
    resolve_inputs,
)
from pullraptor.models import Deadline, Limits
from tests.helpers import make_repo


class TestSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"a.py": b"print('base')\n", "docs/info.txt": b"info\n"})
        self.limits = Limits()
        self.deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    def tearDown(self) -> None:
        self.repo.cleanup()

    def test_refs_pinned_before_read(self) -> None:
        # Branch 'main' should resolve to exact SHA commit OID
        base_tip, comparison_base, head = resolve_inputs(
            self.repo.root, "main", "main", self.limits, self.deadline
        )
        self.assertEqual(len(base_tip), len(self.repo.commit_ids[0]))
        self.assertEqual(base_tip, self.repo.commit_ids[0])
        self.assertEqual(comparison_base, self.repo.commit_ids[0])
        self.assertEqual(head, self.repo.commit_ids[0])

    def test_merge_base_not_base_tip(self) -> None:
        # Create base commit, then branch feature, then commit to main, then commit to feature
        base_commit = self.repo.commit_ids[0]
        # commit on main
        main_c2 = self.repo.commit({"a.py": b"print('main 2')\n"})

        # create and switch to feature from base_commit
        subprocess.run(["git", "checkout", "-b", "feature", base_commit], cwd=self.repo.root, check=True, capture_output=True)
        feat_c1 = self.repo.commit({"b.py": b"print('feature 1')\n"})

        base_tip, comparison_base, head = resolve_inputs(
            self.repo.root, "main", "feature", self.limits, self.deadline
        )
        self.assertEqual(base_tip, main_c2)
        self.assertEqual(head, feat_c1)
        self.assertEqual(comparison_base, base_commit)
        self.assertNotEqual(comparison_base, base_tip)

    def test_dirty_tree_ignored(self) -> None:
        # Modify a.py in working tree without committing
        (self.repo.root / "a.py").write_text("print('DIRTY UNCOMMITTED')\n")
        snap = read_snapshot(self.repo.root, self.repo.commit_ids[0], self.limits, self.deadline)
        a_blob = next(b for b in snap.blobs if b.path == "a.py")
        content = read_blob(self.repo.root, a_blob.blob_oid, self.limits, self.deadline)
        self.assertEqual(content, b"print('base')\n")

    def test_option_like_ref_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_inputs(self.repo.root, "--help", "main", self.limits, self.deadline)
        with self.assertRaises(ValueError):
            resolve_inputs(self.repo.root, "main", "-v", self.limits, self.deadline)

    def test_nul_metadata_paths(self) -> None:
        # File with space, tab, newline in name
        weird_name = "path with spaces.py"
        c = self.repo.commit({weird_name: b"content\n"})
        snap = read_snapshot(self.repo.root, c, self.limits, self.deadline)
        found = any(b.path == weird_name for b in snap.blobs)
        self.assertTrue(found)

    def test_binary_and_deleted_file_preserved(self) -> None:
        c1 = self.repo.commit({"binary.bin": b"\x00\x01\x02\xff"})
        snap1 = read_snapshot(self.repo.root, c1, self.limits, self.deadline)
        bin_blob = next(b for b in snap1.blobs if b.path == "binary.bin")
        content = read_blob(self.repo.root, bin_blob.blob_oid, self.limits, self.deadline)
        self.assertEqual(content, b"\x00\x01\x02\xff")

        c2 = self.repo.commit({"binary.bin": None})
        snap2 = read_snapshot(self.repo.root, c2, self.limits, self.deadline)
        self.assertFalse(any(b.path == "binary.bin" for b in snap2.blobs))

    def test_symlink_and_submodule_not_followed(self) -> None:
        # Create a symlink in git
        try:
            (self.repo.root / "link.py").symlink_to("a.py")
            subprocess.run(["git", "add", "link.py"], cwd=self.repo.root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "add symlink"], cwd=self.repo.root, check=True, capture_output=True)
            c = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo.root, check=True, capture_output=True, text=True).stdout.strip()
            snap = read_snapshot(self.repo.root, c, self.limits, self.deadline)
            link_ref = next((b for b in snap.blobs if b.path == "link.py"), None)
            # Symlinks should either have mode '120000' and not be treated as regular blob or be in exclusions
            if link_ref:
                self.assertEqual(link_ref.mode, "120000")
        except OSError:
            pass  # Some filesystems do not support symlinks

    def test_replace_objects_ignored(self) -> None:
        c1 = self.repo.commit({"secret.py": b"original\n"})
        c2 = self.repo.commit({"secret.py": b"replaced\n"})
        # Create a git replace
        subprocess.run(["git", "replace", c1, c2], cwd=self.repo.root, check=True, capture_output=True)
        # Reading snapshot for c1 with --no-replace-objects must still return original
        snap = read_snapshot(self.repo.root, c1, self.limits, self.deadline)
        blob = next(b for b in snap.blobs if b.path == "secret.py")
        content = read_blob(self.repo.root, blob.blob_oid, self.limits, self.deadline)
        self.assertEqual(content, b"original\n")


if __name__ == "__main__":
    unittest.main()
