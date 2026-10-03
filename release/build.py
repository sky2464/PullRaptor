"""Release tooling entry point (delegates to installed pullraptor package)."""

from __future__ import annotations

from pullraptor.release_provenance import (
    ArtifactIdentity,
    BuildOrigin,
    ReleaseDecision,
    ReleaseManifest,
    load_manifest,
    manifest_from_dict,
    verify_release,
)

__all__ = (
    "ArtifactIdentity",
    "BuildOrigin",
    "ReleaseDecision",
    "ReleaseManifest",
    "load_manifest",
    "manifest_from_dict",
    "verify_release",
)
