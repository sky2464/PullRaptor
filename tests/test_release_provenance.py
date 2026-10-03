"""Tests for release provenance verification (E07-A2)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from pullraptor.release_provenance import (
    ArtifactIdentity,
    BuildOrigin,
    ReleaseManifest,
    load_manifest,
    verify_release,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "release" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("release_build", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load release/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _origin_env(run_id: str) -> dict[str, str]:
    return {
        "PULLRAPTOR_WORKFLOW_DIGEST": "wf-digest-candidate",
        "PULLRAPTOR_RUN_ID": run_id,
        "PULLRAPTOR_REPOSITORY_ID": "owner/pullraptor",
    }


def _manifest(revision: str, digest: str, size: int) -> ReleaseManifest:
    return ReleaseManifest(
        version="0.2.0",
        source_revision=revision,
        artifacts=(
            ArtifactIdentity(kind="wheel", digest=digest, size=size, entrypoints=("pullraptor",)),
        ),
        runtime_matrix=("python-3.12",),
        dependency_inventory=("stdlib-only",),
        provenance_ref="workflow://example",
    )


class TestReleaseProvenance(unittest.TestCase):
    def test_mutable_tag_insufficient(self) -> None:
        digest = hashlib.sha256(b"wheel-bytes").hexdigest()
        manifest = _manifest("a" * 40, digest, len(b"wheel-bytes"))
        origin = BuildOrigin(
            workflow_digest="wf-digest",
            run_id="1",
            repository_id="owner/repo",
            artifact_digests=("mutable-tag",),
        )
        decision = verify_release(manifest, "a" * 40, origin)
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.cause, "wrong_build_origin")

    def test_wrong_revision_or_build_origin(self) -> None:
        digest = hashlib.sha256(b"wheel-bytes").hexdigest()
        manifest = _manifest("b" * 40, digest, len(b"wheel-bytes"))
        origin = BuildOrigin(
            workflow_digest="wf-digest",
            run_id="1",
            repository_id="owner/repo",
            artifact_digests=(digest,),
        )
        decision = verify_release(manifest, "a" * 40, origin)
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.cause, "wrong_source_revision")

    def test_artifact_tampering(self) -> None:
        payload = b"wheel-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = _manifest("a" * 40, digest, len(payload))
        origin = BuildOrigin(
            workflow_digest="wf-digest",
            run_id="1",
            repository_id="owner/repo",
            artifact_digests=(digest,),
        )
        decision = verify_release(
            manifest,
            "a" * 40,
            origin,
            artifact_bytes={digest: b"tampered"},
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.cause, "artifact_tampering")

    def test_build_dependency_inventory(self) -> None:
        digest = hashlib.sha256(b"x").hexdigest()
        manifest = ReleaseManifest(
            version="0.2.0",
            source_revision="a" * 40,
            artifacts=(ArtifactIdentity("wheel", digest, 1, ()),),
            runtime_matrix=("python-3.12",),
            dependency_inventory=(),
            provenance_ref="",
        )
        origin = BuildOrigin("wf", "1", "owner/repo", (digest,))
        decision = verify_release(manifest, "a" * 40, origin)
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.cause, "missing_dependency_inventory")

    def test_two_builds_reported(self) -> None:
        payload = b"same-input"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = _manifest("a" * 40, digest, len(payload))
        origin = BuildOrigin("wf", "1", "owner/repo", (digest,))
        first = verify_release(manifest, "a" * 40, origin, artifact_bytes={digest: payload})
        second = verify_release(manifest, "a" * 40, origin, artifact_bytes={digest: payload})
        self.assertTrue(first.admitted)
        self.assertTrue(second.admitted)
        self.assertEqual(first.cause, second.cause)


class TestReleaseBuilder(unittest.TestCase):
    def test_release_builder_failure_is_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT), "--source-revision", "not-a-git-hash"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release candidate build failed", result.stderr)

    def test_release_builder_emits_complete_manifest(self) -> None:
        build = _load_build_module()
        produce_release_candidate = build.produce_release_candidate

        out = REPO_ROOT / "build" / "test-release-candidate"
        if out.exists():
            for path in out.iterdir():
                path.unlink()
        revision = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        manifest, origin, artifact_bytes = produce_release_candidate(
            REPO_ROOT,
            out,
            source_revision=revision,
            environ=_origin_env("builder-test-1"),
        )
        self.assertTrue((out / "manifest.json").is_file())
        self.assertTrue((out / "build-receipt.json").is_file())
        receipt = json.loads((out / "build-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["product_acceptance"], "pending")
        self.assertTrue(receipt["candidate_only"])
        loaded = load_manifest(out / "manifest.json")
        self.assertEqual(loaded.version, manifest.version)
        self.assertEqual(loaded.source_revision, revision)
        self.assertGreaterEqual(len(loaded.artifacts), 1)
        self.assertTrue(loaded.dependency_inventory)
        decision = verify_release(
            loaded,
            revision,
            origin,
            artifact_bytes=artifact_bytes,
        )
        self.assertTrue(decision.admitted)

    def test_two_build_evidence_distinct_origins(self) -> None:
        build = _load_build_module()
        produce_release_candidate = build.produce_release_candidate

        first_dir = REPO_ROOT / "build" / "test-release-origin-a"
        second_dir = REPO_ROOT / "build" / "test-release-origin-b"
        revision = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        produce_release_candidate(
            REPO_ROOT,
            first_dir,
            source_revision=revision,
            environ=_origin_env("origin-run-a"),
        )
        produce_release_candidate(
            REPO_ROOT,
            second_dir,
            source_revision=revision,
            environ=_origin_env("origin-run-b"),
        )
        first_receipt = json.loads((first_dir / "build-receipt.json").read_text(encoding="utf-8"))
        second_receipt = json.loads((second_dir / "build-receipt.json").read_text(encoding="utf-8"))
        self.assertNotEqual(first_receipt["run_id"], second_receipt["run_id"])
        first_manifest = load_manifest(first_dir / "manifest.json")
        second_manifest = load_manifest(second_dir / "manifest.json")
        self.assertNotEqual(first_manifest.provenance_ref, second_manifest.provenance_ref)

    def test_candidate_workflow_no_placeholder_success(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "release-candidate.yml").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("manifest generation requires coordinator release assignment", workflow)
        self.assertNotIn("2>/dev/null", workflow)
        self.assertNotIn("placeholder", workflow.lower())
        self.assertIn("PULLRAPTOR_WORKFLOW_DIGEST", workflow)
        self.assertIn("release/build.py", workflow)


if __name__ == "__main__":
    unittest.main()
