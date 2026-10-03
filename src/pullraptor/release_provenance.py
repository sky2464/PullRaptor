"""Trusted release manifest verification (E07; not part of the review kernel)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
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


_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return sha256_digest(data)


def validate_source_revision(revision: str) -> None:
    if not _REVISION_PATTERN.fullmatch(revision):
        raise ValueError("source_revision must be a 40-character lowercase git commit hash")


def validate_artifact_digest(digest: str) -> None:
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise ValueError("artifact digest must be a 64-character lowercase sha256 hex string")


def manifest_to_dict(manifest: ReleaseManifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "source_revision": manifest.source_revision,
        "provenance_ref": manifest.provenance_ref,
        "runtime_matrix": list(manifest.runtime_matrix),
        "dependency_inventory": list(manifest.dependency_inventory),
        "artifacts": [
            {
                "kind": artifact.kind,
                "digest": artifact.digest,
                "size": artifact.size,
                "entrypoints": list(artifact.entrypoints),
            }
            for artifact in manifest.artifacts
        ],
    }


def dump_manifest(manifest: ReleaseManifest, path: Path) -> None:
    path.write_text(
        json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def provenance_ref_from_origin(origin: BuildOrigin) -> str:
    return f"workflow://{origin.repository_id}/run/{origin.run_id}"


def load_build_origin_from_environ(
    artifact_digests: tuple[str, ...],
    *,
    environ: dict[str, str] | None = None,
) -> BuildOrigin:
    """Read trusted build origin from operator-controlled environment variables."""
    env = environ if environ is not None else os.environ
    workflow_digest = (
        env.get("PULLRAPTOR_WORKFLOW_DIGEST")
        or env.get("GITHUB_WORKFLOW_SHA")
        or ""
    ).strip()
    run_id = (env.get("PULLRAPTOR_RUN_ID") or env.get("GITHUB_RUN_ID") or "").strip()
    repository_id = (
        env.get("PULLRAPTOR_REPOSITORY_ID") or env.get("GITHUB_REPOSITORY") or ""
    ).strip()
    if not workflow_digest or not run_id or not repository_id:
        raise ValueError("missing_trusted_build_origin")
    return BuildOrigin(
        workflow_digest=workflow_digest,
        run_id=run_id,
        repository_id=repository_id,
        artifact_digests=artifact_digests,
    )


def dependency_inventory_from_inventory_doc(data: dict[str, Any]) -> tuple[str, ...]:
    entries: list[str] = []
    kernel = data.get("kernel_runtime", {})
    if kernel.get("python_packages") == []:
        entries.append("kernel-runtime:stdlib-only")
    for tool in data.get("build_tools", []):
        name = str(tool.get("name", "unknown"))
        constraint = str(tool.get("version_constraint", tool.get("version", "unknown")))
        entries.append(f"build:{name}:{constraint}")
    if not entries:
        raise ValueError("empty_dependency_inventory")
    return tuple(entries)


def runtime_matrix_from_inventory_doc(data: dict[str, Any]) -> tuple[str, ...]:
    minors: set[str] = set()
    for profile in data.get("supported_profiles", []):
        python_spec = str(profile.get("python", ""))
        if python_spec.startswith("3."):
            minors.add(python_spec.split(".")[0] + "." + python_spec.split(".")[1])
    if not minors:
        return ("python-3.12",)
    return tuple(f"python-{minor}" for minor in sorted(minors))


def entrypoints_from_inventory_doc(data: dict[str, Any]) -> tuple[str, ...]:
    commands = tuple(str(item["command"]) for item in data.get("entry_points", []) if item.get("command"))
    return commands if commands else ("pullraptor",)


def artifact_identity_from_bytes(
    kind: str,
    payload: bytes,
    *,
    entrypoints: tuple[str, ...],
) -> ArtifactIdentity:
    digest = sha256_digest(payload)
    validate_artifact_digest(digest)
    return ArtifactIdentity(kind=kind, digest=digest, size=len(payload), entrypoints=entrypoints)


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
