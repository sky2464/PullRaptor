"""Exact scoped patch preconditions and immutable tree application (E06-T1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from pullraptor.models import BlobRef, Snapshot

_ABSENT_BLOB_OID = "0000000000000000000000000000000000000000"
_REGULAR_FILE_MODE = "100644"
_ADDITION_MODE = "100644"
_MAX_PROPOSAL_BYTES = 1_048_576
_MAX_PATHS = 10
_MAX_CHANGED_LINES = 2_000

_PROTECTED_PREFIXES = (".git/", ".github/workflows/")
_TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)|%2f|%2F|\\")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class PathEdit:
    """Single full-file replacement or addition."""

    path: str
    old_blob: str
    old_mode: str
    new_bytes: bytes


@dataclass(frozen=True)
class PatchProposal:
    """Untrusted patch proposal bound to an exact head revision."""

    head: str
    digest: str
    allowed_paths: frozenset[str]
    edits: tuple[PathEdit, ...]


@dataclass(frozen=True)
class StageResult:
    """Per-stage validation outcome."""

    stage: str
    status: str
    cause: str


@dataclass(frozen=True)
class PatchedTree:
    """Immutable trees produced when P0/P1 succeed."""

    original_tree: str
    result_tree: str
    patch_digest: str
    stages: tuple[StageResult, ...]
    synthetic: bool = True


def _path_bytes(path: str) -> bytes:
    return path.encode("utf-8")


def _blob_index(snapshot: Snapshot) -> dict[bytes, BlobRef]:
    return {blob.path_bytes: blob for blob in snapshot.blobs}


def _is_protected_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    for prefix in _PROTECTED_PREFIXES:
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return True
    return False


def _path_grant_denied(path: str, trusted_allowed_paths: frozenset[str]) -> bool:
    if path not in trusted_allowed_paths:
        return True
    if _is_protected_path(path):
        return True
    if path.startswith("/") or _TRAVERSAL_RE.search(path):
        return True
    return False


def _unsupported_mode(mode: str) -> bool:
    return mode not in (_REGULAR_FILE_MODE,)


def _count_changed_lines(old: bytes, new: bytes) -> int:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    return abs(len(old_lines) - len(new_lines)) + sum(
        1 for left, right in zip(old_lines, new_lines) if left != right
    )


def _proposal_size_bytes(proposal: PatchProposal) -> int:
    total = len(proposal.head) + len(proposal.digest)
    for edit in proposal.edits:
        total += len(edit.path) + len(edit.old_blob) + len(edit.old_mode) + len(edit.new_bytes)
    return total


def _patch_digest(proposal: PatchProposal) -> str:
    parts: list[str] = [proposal.head, proposal.digest]
    for edit in sorted(proposal.edits, key=lambda e: e.path):
        parts.extend(
            [
                edit.path,
                edit.old_blob,
                edit.old_mode,
                hashlib.sha256(edit.new_bytes).hexdigest(),
            ]
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _synthetic_blob_oid(content: bytes) -> str:
    return hashlib.sha256(b"synthetic-blob:" + content).hexdigest()


def _synthetic_tree_oid(entries: tuple[tuple[bytes, str, str], ...]) -> str:
    payload = b"\n".join(
        path + b"\0" + mode.encode("ascii") + b"\0" + oid.encode("ascii")
        for path, mode, oid in entries
    )
    return "synthetic-tree:" + hashlib.sha256(payload).hexdigest()


def _apply_edits(snapshot: Snapshot, edits: tuple[PathEdit, ...]) -> str:
    by_path = dict(_blob_index(snapshot))
    for edit in edits:
        content = edit.new_bytes
        oid = _synthetic_blob_oid(content)
        by_path[_path_bytes(edit.path)] = BlobRef(
            path=edit.path,
            path_bytes=_path_bytes(edit.path),
            mode=_REGULAR_FILE_MODE,
            blob_oid=oid,
            size=len(content),
        )
    entries = tuple(
        sorted(
            (blob.path_bytes, blob.mode, blob.blob_oid)
            for blob in by_path.values()
        )
    )
    return _synthetic_tree_oid(entries)


def validate_patch(
    proposal: PatchProposal,
    head: Snapshot,
    *,
    trusted_allowed_paths: frozenset[str],
) -> tuple[StageResult, ...]:
    """Validate P0 preconditions; P1 is not_run when P0 fails."""
    stages: list[StageResult] = []

    if not _SHA_RE.match(proposal.head):
        stages.append(StageResult("P0", "failed", "invalid_head"))
        stages.append(StageResult("P1", "not_run", "p0_failed"))
        return tuple(stages)

    if head.oid != proposal.head:
        stages.append(StageResult("P0", "stale", "head_mismatch"))
        stages.append(StageResult("P1", "not_run", "p0_stale"))
        return tuple(stages)

    if _proposal_size_bytes(proposal) > _MAX_PROPOSAL_BYTES:
        stages.append(StageResult("P0", "failed", "proposal_too_large"))
        stages.append(StageResult("P1", "not_run", "p0_failed"))
        return tuple(stages)

    if len(proposal.edits) > _MAX_PATHS:
        stages.append(StageResult("P0", "failed", "too_many_paths"))
        stages.append(StageResult("P1", "not_run", "p0_failed"))
        return tuple(stages)

    index = _blob_index(head)
    changed_lines = 0

    for edit in proposal.edits:
        if _path_grant_denied(edit.path, trusted_allowed_paths):
            stages.append(StageResult("P0", "failed", "path_not_granted"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        if _unsupported_mode(edit.old_mode):
            stages.append(StageResult("P0", "failed", "unsupported_mode"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        entry = index.get(_path_bytes(edit.path))
        is_addition = edit.old_blob == _ABSENT_BLOB_OID

        if is_addition:
            if edit.old_mode != _ADDITION_MODE:
                stages.append(StageResult("P0", "failed", "invalid_addition_mode"))
                stages.append(StageResult("P1", "not_run", "p0_failed"))
                return tuple(stages)
            if entry is not None:
                stages.append(StageResult("P0", "failed", "path_exists"))
                stages.append(StageResult("P1", "not_run", "p0_failed"))
                return tuple(stages)
            changed_lines += len(edit.new_bytes.splitlines())
            continue

        if entry is None:
            stages.append(StageResult("P0", "failed", "missing_path"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        if entry.mode in ("120000", "160000"):
            stages.append(StageResult("P0", "failed", "unsupported_entry_type"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        if entry.mode != edit.old_mode or entry.blob_oid != edit.old_blob:
            stages.append(StageResult("P0", "failed", "blob_mode_mismatch"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        if not edit.new_bytes:
            stages.append(StageResult("P0", "failed", "deletion_not_admitted"))
            stages.append(StageResult("P1", "not_run", "p0_failed"))
            return tuple(stages)

        changed_lines += _count_changed_lines(b"", edit.new_bytes)

    if changed_lines > _MAX_CHANGED_LINES:
        stages.append(StageResult("P0", "failed", "too_many_changed_lines"))
        stages.append(StageResult("P1", "not_run", "p0_failed"))
        return tuple(stages)

    stages.append(StageResult("P0", "passed", "ok"))
    stages.append(StageResult("P1", "passed", "ok"))
    return tuple(stages)


def apply_patch_tree(
    proposal: PatchProposal,
    head: Snapshot,
    *,
    trusted_allowed_paths: frozenset[str],
) -> PatchedTree:
    """Apply edits to a synthetic immutable tree when P0/P1 preconditions pass."""
    stages = validate_patch(proposal, head, trusted_allowed_paths=trusted_allowed_paths)
    stage_map = {stage.stage: stage for stage in stages}
    original_tree = head.oid

    if stage_map.get("P0", StageResult("P0", "failed", "")).status != "passed":
        return PatchedTree(
            original_tree=original_tree,
            result_tree=original_tree,
            patch_digest=_patch_digest(proposal),
            stages=stages,
        )

    if stage_map.get("P1", StageResult("P1", "not_run", "")).status != "passed":
        return PatchedTree(
            original_tree=original_tree,
            result_tree=original_tree,
            patch_digest=_patch_digest(proposal),
            stages=stages,
        )

    result_tree = _apply_edits(head, proposal.edits)
    return PatchedTree(
        original_tree=original_tree,
        result_tree=result_tree,
        patch_digest=_patch_digest(proposal),
        stages=stages,
    )
