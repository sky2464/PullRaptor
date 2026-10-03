"""PullRaptor safe immutable Git snapshot ingestion."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

from pullraptor.models import (
    BlobRef,
    Deadline,
    Diagnostic,
    Limits,
    ProcessBounds,
    Snapshot,
)
from pullraptor.process import run_bounded

_GIT_BIN = shutil.which("git") or "/usr/bin/git"


def _git_env() -> dict[str, str]:
    """Produce a sanitized minimal environment for Git subprocesses."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "HOME": "/dev/null",
    }


def _safe_git_args() -> list[str]:
    """Base arguments to disable external helpers, replacement objects, and hooks."""
    return [
        _GIT_BIN,
        "-c", "core.fsmonitor=false",
        "-c", "diff.external=",
        "-c", "diff.textconv=",
        "--no-lazy-fetch",
        "--no-replace-objects",
        "--no-optional-locks",
    ]


def resolve_inputs(
    repo: Path,
    base_ref: str,
    head_ref: str,
    limits: Limits,
    deadline: Deadline,
    *,
    exact_base: bool = False,
) -> tuple[str, str, str]:
    """Resolve base and head refs to immutable commit OIDs and compute comparison base.

    Returns (base_tip_oid, comparison_base_oid, head_oid).
    """
    if base_ref.startswith("-") or head_ref.startswith("-"):
        raise ValueError(f"Option-like ref rejected: base={base_ref!r}, head={head_ref!r}")

    env = _git_env()
    bounds = ProcessBounds(max_stdout_bytes=1024, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)

    # Resolve base_ref commit OID
    cmd_base = tuple(_safe_git_args() + ["rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"])
    res_base = run_bounded(cmd_base, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res_base.returncode != 0:
        raise ValueError(f"Failed to resolve base ref {base_ref!r}: {res_base.stderr.decode('utf-8', errors='replace').strip()}")
    base_tip = res_base.stdout.decode("utf-8").strip()

    # Resolve head_ref commit OID
    cmd_head = tuple(_safe_git_args() + ["rev-parse", "--verify", "--end-of-options", f"{head_ref}^{{commit}}"])
    res_head = run_bounded(cmd_head, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res_head.returncode != 0:
        raise ValueError(f"Failed to resolve head ref {head_ref!r}: {res_head.stderr.decode('utf-8', errors='replace').strip()}")
    head_oid = res_head.stdout.decode("utf-8").strip()

    if exact_base:
        return (base_tip, base_tip, head_oid)

    # Compute merge-base
    cmd_mb = tuple(_safe_git_args() + ["merge-base", "--all", base_tip, head_oid])
    res_mb = run_bounded(cmd_mb, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res_mb.returncode != 0:
        raise ValueError(f"Failed to compute merge-base between {base_tip} and {head_oid}")

    lines = [line.strip() for line in res_mb.stdout.decode("utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"No common merge-base ancestor found between {base_tip} and {head_oid}")
    if len(lines) > 1:
        raise ValueError(f"Multiple merge bases rejected; exact base required. Found: {lines}")

    comparison_base = lines[0]
    return (base_tip, comparison_base, head_oid)


def read_snapshot(repo: Path, oid: str, limits: Limits, deadline: Deadline) -> Snapshot:
    """Read immutable tree snapshot for a commit OID using NUL-delimited ls-tree."""
    env = _git_env()
    # Read ls-tree with -l for size
    bounds = ProcessBounds(
        max_stdout_bytes=limits.max_total_bytes,
        max_stderr_bytes=limits.max_stderr_bytes,
        timeout_seconds=limits.review_timeout_seconds,
    )
    cmd = tuple(_safe_git_args() + ["ls-tree", "-r", "-z", "-l", "--full-name", oid])
    res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res.returncode != 0:
        raise ValueError(f"Failed to read snapshot {oid}: {res.stderr.decode('utf-8', errors='replace').strip()}")

    blobs: list[BlobRef] = []
    diagnostics: list[Diagnostic] = []

    # Parse NUL-delimited records
    raw_records = res.stdout.split(b"\x00")
    for raw in raw_records:
        if not raw:
            continue
        try:
            meta, path_bytes = raw.split(b"\t", 1)
        except ValueError:
            continue

        meta_parts = meta.split()
        if len(meta_parts) < 4:
            continue

        mode = meta_parts[0].decode("ascii", errors="replace")
        entry_type = meta_parts[1].decode("ascii", errors="replace")
        blob_oid = meta_parts[2].decode("ascii", errors="replace")
        size_str = meta_parts[3].decode("ascii", errors="replace")
        size = int(size_str) if size_str.isdigit() else 0

        # Try decoding path as UTF-8
        try:
            path = path_bytes.decode("utf-8")
        except UnicodeDecodeError:
            path = None
            diagnostics.append(
                Diagnostic(
                    code="PATH_NON_UTF8",
                    message="Path contains non-UTF-8 bytes",
                    path=None,
                    cause="non_utf8_path",
                )
            )

        # Symlinks (120000) or submodules (160000) are not normal source blobs
        blobs.append(
            BlobRef(
                path=path,
                path_bytes=path_bytes,
                mode=mode,
                blob_oid=blob_oid,
                size=size,
            )
        )

    if len(blobs) > limits.max_tracked_entries:
        diagnostics.append(
            Diagnostic(
                code="LIMIT_EXCEEDED",
                message=f"Tracked entries ({len(blobs)}) exceeds maximum ({limits.max_tracked_entries})",
                cause="max_tracked_entries_exceeded",
            )
        )

    return Snapshot(oid=oid, blobs=tuple(blobs), diagnostics=tuple(diagnostics))


def read_blob(repo: Path, blob_oid: str, limits: Limits, deadline: Deadline) -> bytes:
    """Read blob bytes from immutable Git storage with size bounds."""
    env = _git_env()
    bounds = ProcessBounds(
        max_stdout_bytes=limits.max_blob_bytes,
        max_stderr_bytes=limits.max_stderr_bytes,
        timeout_seconds=limits.parse_timeout_seconds,
    )
    cmd = tuple(_safe_git_args() + ["cat-file", "-p", blob_oid])
    res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)

    if res.stdout_truncated:
        raise ValueError(f"Blob {blob_oid} size exceeded max_blob_bytes ({limits.max_blob_bytes})")
    if res.returncode != 0:
        raise ValueError(f"Failed to read blob {blob_oid}: {res.stderr.decode('utf-8', errors='replace').strip()}")

    return res.stdout
