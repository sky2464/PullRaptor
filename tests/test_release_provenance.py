"""Tests for release provenance verification (E07-A2)."""

from __future__ import annotations

import hashlib
import unittest

from pullraptor.release_provenance import (
    ArtifactIdentity,
    BuildOrigin,
    ReleaseManifest,
    verify_release,
)


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


if __name__ == "__main__":
    unittest.main()
