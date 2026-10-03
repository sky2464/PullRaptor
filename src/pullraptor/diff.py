"""PullRaptor safe diff facts and hunk isolation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from pullraptor.git_snapshot import _git_env, _safe_git_args
from pullraptor.models import (
    BlobRef,
    Change,
    Deadline,
    Limits,
    ProcessBounds,
    Snapshot,
)
from pullraptor.process import run_bounded

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_EMPTY_BLOB_SHA1 = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


@dataclass(frozen=True)
class DiffHunk:
    """Parsed unified diff hunk."""
    base_start: int
    base_count: int
    head_start: int
    head_count: int
    lines: tuple[str, ...]


def _parse_hunks(diff_text: str) -> tuple[DiffHunk, ...]:
    """Parse unified diff text into structured DiffHunk records."""
    hunks: list[DiffHunk] = []
    current_lines: list[str] = []
    current_header: tuple[int, int, int, int] | None = None

    for line in diff_text.splitlines():
        match = _HUNK_RE.match(line)
        if match:
            if current_header is not None:
                b_s, b_c, h_s, h_c = current_header
                hunks.append(DiffHunk(b_s, b_c, h_s, h_c, tuple(current_lines)))
                current_lines = []

            b_start = int(match.group(1))
            b_count = int(match.group(2)) if match.group(2) else 1
            h_start = int(match.group(3))
            h_count = int(match.group(4)) if match.group(4) else 1
            current_header = (b_start, b_count, h_start, h_count)
        elif current_header is not None:
            if line.startswith(("+", "-", " ", "\\")):
                current_lines.append(line)

    if current_header is not None:
        b_s, b_c, h_s, h_c = current_header
        hunks.append(DiffHunk(b_s, b_c, h_s, h_c, tuple(current_lines)))

    return tuple(hunks)


def _compute_blob_diff(
    repo: Path,
    base_oid: str | None,
    head_oid: str | None,
    limits: Limits,
    deadline: Deadline,
) -> tuple[DiffHunk, ...]:
    """Compute isolated diff between two blob object IDs without repository attributes."""
    # Use empty blob if added or deleted
    oid1 = base_oid if base_oid else _EMPTY_BLOB_SHA1
    oid2 = head_oid if head_oid else _EMPTY_BLOB_SHA1

    if oid1 == oid2:
        return ()

    env = _git_env()
    bounds = ProcessBounds(
        max_stdout_bytes=min(limits.max_blob_bytes * 2, limits.max_diff_bytes),
        max_stderr_bytes=limits.max_stderr_bytes,
        timeout_seconds=limits.parse_timeout_seconds,
    )
    # Using git diff with raw blob hashes isolates comparison from working tree attributes
    cmd = tuple(_safe_git_args() + ["diff", "--no-color", "--no-ext-diff", "-U3", oid1, oid2])
    res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)

    diff_text = res.stdout.decode("utf-8", errors="replace")
    return _parse_hunks(diff_text)


def changes(
    repo: Path,
    base: Snapshot,
    head: Snapshot,
    limits: Limits,
    deadline: Deadline,
) -> tuple[Change, ...]:
    """Derive exact changed identity and hunks between base and head snapshots."""
    base_by_path: dict[bytes, BlobRef] = {b.path_bytes: b for b in base.blobs}
    head_by_path: dict[bytes, BlobRef] = {b.path_bytes: b for b in head.blobs}

    all_paths = sorted(set(base_by_path.keys()) | set(head_by_path.keys()))
    results: list[Change] = []
    total_diff_bytes = 0

    for path_bytes in all_paths:
        base_blob = base_by_path.get(path_bytes)
        head_blob = head_by_path.get(path_bytes)

        if base_blob is None and head_blob is not None:
            kind = "added"
            path = head_blob.path
            hunks = _compute_blob_diff(repo, None, head_blob.blob_oid, limits, deadline)
        elif base_blob is not None and head_blob is None:
            kind = "deleted"
            path = base_blob.path
            hunks = _compute_blob_diff(repo, base_blob.blob_oid, None, limits, deadline)
        elif base_blob is not None and head_blob is not None:
            if base_blob.blob_oid == head_blob.blob_oid and base_blob.mode == head_blob.mode:
                continue
            path = head_blob.path or base_blob.path
            if base_blob.mode != head_blob.mode and base_blob.blob_oid == head_blob.blob_oid:
                kind = "type_changed"
                hunks = ()
            else:
                kind = "modified"
                hunks = _compute_blob_diff(repo, base_blob.blob_oid, head_blob.blob_oid, limits, deadline)
        else:
            continue

        # Check total diff bytes budget
        hunk_bytes = sum(len(line.encode("utf-8")) for h in hunks for line in h.lines)
        if total_diff_bytes + hunk_bytes > limits.max_diff_bytes:
            # Bounded output reached: omit further hunks
            hunks = ()
        else:
            total_diff_bytes += hunk_bytes

        results.append(
            Change(
                path=path,
                path_bytes=path_bytes,
                kind=kind,
                base_blob=base_blob,
                head_blob=head_blob,
                hunks=hunks,
            )
        )

    return tuple(results)
