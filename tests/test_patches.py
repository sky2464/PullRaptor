"""E06-T1 patch precondition and immutable application tests."""

from __future__ import annotations

import subprocess
import unittest

from pullraptor.models import BlobRef, Snapshot
from pullraptor.patches import (
    PathEdit,
    PatchProposal,
    apply_patch_tree,
    validate_patch,
)
from tests.helpers import make_repo


def _blob_oid(repo_root, rel_path: str) -> str:
    res = subprocess.run(
        ["git", "hash-object", rel_path],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def _head_tree_oid(repo_root) -> str:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def _snapshot_for_head(repo_root, head_oid: str) -> Snapshot:
    tree_oid = subprocess.run(
        ["git", "rev-parse", f"{head_oid}^{{tree}}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    ls = subprocess.run(
        ["git", "ls-tree", tree_oid],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().splitlines()
    blobs: list[BlobRef] = []
    for line in ls:
        mode, obj_type, oid, path = line.split(maxsplit=3)
        if obj_type != "blob":
            continue
        size = int(
            subprocess.run(
                ["git", "cat-file", "-s", oid],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        blobs.append(
            BlobRef(
                path=path,
                path_bytes=path.encode("utf-8"),
                mode=mode,
                blob_oid=oid,
                size=size,
            )
        )
    return Snapshot(oid=head_oid, blobs=tuple(blobs))


def _stages_dict(stages: tuple) -> dict[str, object]:
    return {stage.stage: stage for stage in stages}


class TestPatches(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"app.py": b"def f():\n    return 1\n"})
        self.head = self.repo.commit_ids[0]
        self.snapshot = _snapshot_for_head(self.repo.root, self.head)
        self.trusted = frozenset({"app.py"})

    def tearDown(self) -> None:
        self.repo.cleanup()

    def test_old_blob_mode_mismatch(self) -> None:
        proposal = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"app.py"}),
            edits=(
                PathEdit(
                    path="app.py",
                    old_blob="b" * 40,
                    old_mode="100644",
                    new_bytes=b"def f():\n    return 2\n",
                ),
            ),
        )
        stages = _stages_dict(validate_patch(proposal, self.snapshot, trusted_allowed_paths=self.trusted))
        self.assertEqual(stages["P0"].status, "failed")
        self.assertEqual(stages["P0"].cause, "blob_mode_mismatch")
        self.assertEqual(stages["P1"].status, "not_run")

    def test_stale_head(self) -> None:
        new_head = self.repo.commit({"app.py": b"def f():\n    return 9\n"})
        fresh = _snapshot_for_head(self.repo.root, new_head)
        proposal = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"app.py"}),
            edits=(
                PathEdit(
                    path="app.py",
                    old_blob=_blob_oid(self.repo.root, "app.py"),
                    old_mode="100644",
                    new_bytes=b"def f():\n    return 2\n",
                ),
            ),
        )
        before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        stages = _stages_dict(validate_patch(proposal, fresh, trusted_allowed_paths=self.trusted))
        after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(stages["P0"].status, "stale")
        self.assertEqual(stages["P1"].status, "not_run")
        self.assertEqual(before, after)

    def test_traversal_symlink_and_submodule_denied(self) -> None:
        traversal = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"../secret"}),
            edits=(
                PathEdit(
                    path="../secret",
                    old_blob="b" * 40,
                    old_mode="100644",
                    new_bytes=b"x",
                ),
            ),
        )
        stages = _stages_dict(
            validate_patch(traversal, self.snapshot, trusted_allowed_paths=frozenset({"../secret"}))
        )
        self.assertEqual(stages["P0"].status, "failed")
        self.assertIn(stages["P0"].cause, ("path_not_granted",))

        symlink_snapshot = Snapshot(
            oid=self.head,
            blobs=(
                BlobRef(
                    path="link",
                    path_bytes=b"link",
                    mode="120000",
                    blob_oid="a" * 40,
                    size=3,
                ),
            ),
        )
        symlink_edit = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"link"}),
            edits=(
                PathEdit(
                    path="link",
                    old_blob="a" * 40,
                    old_mode="100644",
                    new_bytes=b"text",
                ),
            ),
        )
        stages = _stages_dict(
            validate_patch(symlink_edit, symlink_snapshot, trusted_allowed_paths=frozenset({"link"}))
        )
        self.assertEqual(stages["P0"].cause, "unsupported_entry_type")

    def test_workflow_policy_path_denied(self) -> None:
        proposal = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({".github/workflows/ci.yml"}),
            edits=(
                PathEdit(
                    path=".github/workflows/ci.yml",
                    old_blob="b" * 40,
                    old_mode="100644",
                    new_bytes=b"name: ci\n",
                ),
            ),
        )
        stages = _stages_dict(
            validate_patch(
                proposal,
                self.snapshot,
                trusted_allowed_paths=frozenset({".github/workflows/ci.yml"}),
            )
        )
        self.assertEqual(stages["P0"].status, "failed")
        self.assertEqual(stages["P0"].cause, "path_not_granted")

    def test_exact_no_fuzz_application(self) -> None:
        oid = _blob_oid(self.repo.root, "app.py")
        proposal = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"app.py"}),
            edits=(
                PathEdit(
                    path="app.py",
                    old_blob=oid,
                    old_mode="100644",
                    new_bytes=b"def f():\n    return 1\n# partial",
                ),
            ),
        )
        patched = apply_patch_tree(proposal, self.snapshot, trusted_allowed_paths=self.trusted)
        stages = _stages_dict(patched.stages)
        self.assertEqual(stages["P0"].status, "passed")
        self.assertEqual(stages["P1"].status, "passed")
        self.assertNotEqual(patched.result_tree, patched.original_tree)
        self.assertTrue(patched.synthetic)

    def test_rename_delete_not_admitted(self) -> None:
        delete = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"app.py"}),
            edits=(
                PathEdit(
                    path="app.py",
                    old_blob=_blob_oid(self.repo.root, "app.py"),
                    old_mode="100644",
                    new_bytes=b"",
                ),
            ),
        )
        stages = _stages_dict(validate_patch(delete, self.snapshot, trusted_allowed_paths=self.trusted))
        self.assertEqual(stages["P0"].cause, "deletion_not_admitted")

        rename = PatchProposal(
            head=self.head,
            digest="d",
            allowed_paths=frozenset({"renamed.py"}),
            edits=(
                PathEdit(
                    path="renamed.py",
                    old_blob=_blob_oid(self.repo.root, "app.py"),
                    old_mode="100644",
                    new_bytes=b"def f():\n    return 1\n",
                ),
            ),
        )
        stages = _stages_dict(
            validate_patch(rename, self.snapshot, trusted_allowed_paths=frozenset({"renamed.py"}))
        )
        self.assertEqual(stages["P0"].cause, "missing_path")


if __name__ == "__main__":
    unittest.main()
