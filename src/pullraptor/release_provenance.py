"""Trusted release manifest verification (E07; not part of the review kernel)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactIdentity:
    kind: str
    digest: str
    size: int
    entrypoints: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseManifest:
    version: str
    source_revision: str
    artifacts: tuple[ArtifactIdentity, ...]
    runtime_matrix: tuple[str, ...]
    dependency_inventory: tuple[str, ...]
    provenance_ref: str


@dataclass(frozen=True)
class BuildOrigin:
    workflow_digest: str
    run_id: str
    repository_id: str
    artifact_digests: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseDecision:
    admitted: bool
    cause: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_from_dict(data: dict[str, Any]) -> ReleaseManifest:
    artifacts = tuple(
        ArtifactIdentity(
            kind=str(item["kind"]),
            digest=str(item["digest"]),
            size=int(item["size"]),
            entrypoints=tuple(str(ep) for ep in item.get("entrypoints", ())),
        )
        for item in data.get("artifacts", [])
    )
    return ReleaseManifest(
        version=str(data["version"]),
        source_revision=str(data["source_revision"]),
        artifacts=artifacts,
        runtime_matrix=tuple(str(v) for v in data.get("runtime_matrix", ())),
        dependency_inventory=tuple(str(v) for v in data.get("dependency_inventory", ())),
        provenance_ref=str(data.get("provenance_ref", "")),
    )


def verify_release(
    manifest: ReleaseManifest,
    expected_revision: str,
    trusted_origin: BuildOrigin,
    *,
    artifact_bytes: dict[str, bytes] | None = None,
) -> ReleaseDecision:
    """Verify manifest against independently derived build origin metadata."""
    if manifest.source_revision != expected_revision:
        return ReleaseDecision(admitted=False, cause="wrong_source_revision")

    manifest_digests = {artifact.digest for artifact in manifest.artifacts}
    if set(trusted_origin.artifact_digests) != manifest_digests:
        return ReleaseDecision(admitted=False, cause="wrong_build_origin")

    if artifact_bytes:
        for artifact in manifest.artifacts:
            payload = artifact_bytes.get(artifact.digest)
            if payload is None:
                return ReleaseDecision(admitted=False, cause="artifact_tampering")
            if _sha256_bytes(payload) != artifact.digest:
                return ReleaseDecision(admitted=False, cause="artifact_tampering")
            if len(payload) != artifact.size:
                return ReleaseDecision(admitted=False, cause="artifact_tampering")

    if not manifest.dependency_inventory:
        return ReleaseDecision(admitted=False, cause="missing_dependency_inventory")

    return ReleaseDecision(admitted=True, cause="admitted")


def load_manifest(path: Path) -> ReleaseManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return manifest_from_dict(data)
