"""Bounded immutable local snapshot capture without repository filter execution."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from pullraptor.git_snapshot import _git_env, _safe_git_args
from pullraptor.models import Deadline, Diagnostic, Limits, ProcessBounds
from pullraptor.process import run_bounded

_O_RDONLY = os.O_RDONLY
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_EMPTY_TREE_OID = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass(frozen=True)
class LocalSnapshot:
    """Frozen local content snapshot bound to a base revision."""

    tree_oid: str
    base_tip: str
    manifest_digest: str
    capture_mode: str
    include_untracked: bool
    discovery_complete: bool
    diagnostics: tuple[Diagnostic, ...]


def _file_identity(st: os.stat_result) -> tuple[int, int, int]:
    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
    return (st.st_ino, st.st_size, mtime_ns)


def _read_bounded_file(path: Path, limits: Limits) -> tuple[bytes | None, Diagnostic | None, bool]:
    """Read file bytes with no-follow; return (content, diagnostic, race_detected)."""
    try:
        fd = os.open(path, _O_RDONLY | _O_NOFOLLOW)
    except OSError as err:
        return None, Diagnostic(code="READ_FAILED", message=str(err), path=str(path), cause="open_failed"), False

    try:
        before = os.fstat(fd)
        if before.st_size > limits.max_blob_bytes:
            return None, Diagnostic(
                code="LIMIT_EXCEEDED",
                message="File exceeds max_blob_bytes",
                path=str(path),
                cause="max_blob_bytes_exceeded",
            ), False
        if not stat.S_ISREG(before.st_mode):
            if stat.S_ISLNK(before.st_mode):
                return None, Diagnostic(
                    code="UNSUPPORTED_ENTRY",
                    message="Symlink not admitted as blob",
                    path=str(path),
                    cause="symlink",
                ), False
            return None, Diagnostic(
                code="UNSUPPORTED_ENTRY",
                message="Non-regular file not admitted",
                path=str(path),
                cause="non_regular",
            ), False

        chunks: list[bytes] = []
        total = 0
        while True:
            piece = os.read(fd, min(65536, limits.max_blob_bytes - total + 1))
            if not piece:
                break
            total += len(piece)
            if total > limits.max_blob_bytes:
                return None, Diagnostic(
                    code="LIMIT_EXCEEDED",
                    message="File exceeds max_blob_bytes during read",
                    path=str(path),
                    cause="max_blob_bytes_exceeded",
                ), False
            chunks.append(piece)

        after = os.fstat(fd)
        if _file_identity(before) != _file_identity(after):
            return None, Diagnostic(
                code="CAPTURE_RACE",
                message="File identity changed during read",
                path=str(path),
                cause="capture_race",
            ), True
        return b"".join(chunks), None, False
    finally:
        os.close(fd)


def _git_index_path(repo: Path, deadline: Deadline, limits: Limits) -> Path | None:
    env = _git_env()
    bounds = ProcessBounds(max_stdout_bytes=4096, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)
    cmd = tuple(_safe_git_args(repo) + ["rev-parse", "--git-path", "index"])
    res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res.returncode != 0:
        return None
    raw = res.stdout.decode("utf-8", errors="replace").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = (repo / path).resolve()
    return path if path.is_file() else None


@contextmanager
def _isolated_index_environment(repo: Path, deadline: Deadline, limits: Limits):
    """Run Git subprocesses against a copy of the repository index so reads cannot mutate it."""
    base = _git_env()
    index_path = _git_index_path(repo, deadline, limits)
    if index_path is None:
        yield base
        return
    with tempfile.NamedTemporaryFile(prefix="pullraptor_idx_ro_", delete=False) as tf:
        temp_idx = tf.name
    try:
        shutil.copy2(index_path, temp_idx)
        isolated = dict(base)
        isolated["GIT_INDEX_FILE"] = temp_idx
        yield isolated
    finally:
        try:
            os.unlink(temp_idx)
        except OSError:
            pass


def _git_ls_files_index(
    repo: Path,
    limits: Limits,
    deadline: Deadline,
    *,
    env: dict[str, str],
) -> tuple[list[tuple[str, str, str]], list[Diagnostic]]:
    """Return list of (path, mode, blob_oid) from the index."""
    bounds = ProcessBounds(max_stdout_bytes=limits.max_total_bytes, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)
    args = tuple(_safe_git_args(repo) + ["ls-files", "-s", "-z"])
    res = run_bounded(args, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace").strip()
        return [], [Diagnostic(code="GIT_LS_FILES", message=err or "ls-files failed", cause="git_error")]
    entries: list[tuple[str, str, str]] = []
    diagnostics: list[Diagnostic] = []
    for raw in res.stdout.split(b"\x00"):
        if not raw:
            continue
        if b"\t" not in raw:
            continue
        meta, path_bytes = raw.split(b"\t", 1)
        meta_parts = meta.split()
        if len(meta_parts) < 2:
            continue
        mode = meta_parts[0].decode("ascii", errors="replace")
        blob_oid = meta_parts[1].decode("ascii", errors="replace")
        try:
            rel = path_bytes.decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(
                Diagnostic(code="PATH_NON_UTF8", message="Path contains non-UTF-8 bytes", cause="non_utf8_path")
            )
            continue
        entries.append((rel, mode, blob_oid))
    return entries, diagnostics


def _git_tracked_paths(
    repo: Path,
    limits: Limits,
    deadline: Deadline,
    *,
    include_untracked: bool,
    env: dict[str, str],
) -> tuple[list[str], list[Diagnostic]]:
    bounds = ProcessBounds(max_stdout_bytes=limits.max_total_bytes, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)
    args = list(_safe_git_args(repo))
    if include_untracked:
        args.extend(["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    else:
        args.extend(["ls-files", "-z", "--cached"])
    res = run_bounded(tuple(args), cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace").strip()
        return [], [Diagnostic(code="GIT_LS_FILES", message=err or "ls-files failed", cause="git_error")]
    paths: list[str] = []
    diagnostics: list[Diagnostic] = []
    for entry in res.stdout.split(b"\x00"):
        if not entry:
            continue
        try:
            paths.append(entry.decode("utf-8"))
        except UnicodeDecodeError:
            diagnostics.append(
                Diagnostic(code="PATH_NON_UTF8", message="Path contains non-UTF-8 bytes", cause="non_utf8_path")
            )
    return paths, diagnostics


def _git_hash_object_w(
    repo: Path,
    content: bytes,
    deadline: Deadline,
    limits: Limits,
    *,
    env: dict[str, str],
) -> str | None:
    bounds = ProcessBounds(max_stdout_bytes=128, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)
    with tempfile.NamedTemporaryFile(prefix="pullraptor_blob_", delete=False) as tf:
        tf.write(content)
        temp_path = tf.name
    try:
        cmd = tuple(_safe_git_args(repo) + ["hash-object", "-w", temp_path])
        res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)
        if res.returncode != 0:
            return None
        return res.stdout.decode("ascii", errors="replace").strip()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _git_mktree(
    repo: Path,
    lines: bytes,
    deadline: Deadline,
    limits: Limits,
    *,
    env: dict[str, str],
) -> str | None:
    argv = list(_safe_git_args(repo)) + ["mktree", "-z"]
    remaining = deadline.remaining_work()
    if remaining <= 0:
        return None
    try:
        proc = subprocess.run(
            argv,
            cwd=str(repo),
            env=env,
            input=lines,
            capture_output=True,
            timeout=min(5.0, remaining),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("ascii", errors="replace").strip()


def _build_tree_oid(
    repo: Path,
    entries: dict[str, tuple[str, str]],
    deadline: Deadline,
    limits: Limits,
    *,
    env: dict[str, str],
) -> str | None:
    """Build a Git tree OID from a flat map of relative path -> (mode, blob_oid)."""

    def build_level(names: dict[str, tuple[str, str]]) -> str | None:
        direct_files: list[tuple[str, str, str]] = []
        subdirs: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
        for rel, (mode, oid) in names.items():
            if "/" in rel:
                head, rest = rel.split("/", 1)
                subdirs[head][rest] = (mode, oid)
            else:
                direct_files.append((rel, mode, oid))

        lines: list[bytes] = []
        for name, mode, oid in sorted(direct_files, key=lambda x: x[0]):
            lines.append(f"{mode} blob {oid}\t{name}".encode("utf-8"))
            lines.append(b"\x00")

        for sub_name in sorted(subdirs.keys()):
            sub_oid = build_level(subdirs[sub_name])
            if sub_oid is None:
                return None
            lines.append(f"040000 tree {sub_oid}\t{sub_name}".encode("utf-8"))
            lines.append(b"\x00")

        if not lines:
            return _EMPTY_TREE_OID

        payload = b"".join(lines)
        return _git_mktree(repo, payload, deadline, limits, env=env)

    return build_level(entries)


def _manifest_digest(entries: dict[str, tuple[str, str]]) -> str:
    parts = [f"{path}\0{mode}\0{oid}" for path, (mode, oid) in sorted(entries.items())]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def capture_local(
    repo: Path,
    base_tip: str,
    *,
    staged_only: bool,
    include_untracked: bool,
    limits: Limits,
    deadline: Deadline,
) -> LocalSnapshot:
    """Capture admitted local bytes into an immutable Git tree without running filters or mutating the index."""
    repo = repo.resolve()
    capture_mode = "staged" if staged_only else "workdir"
    diagnostics: list[Diagnostic] = []
    race = False
    tree_entries: dict[str, tuple[str, str]] = {}

    with _isolated_index_environment(repo, deadline, limits) as git_env:
        if staged_only:
            index_entries, list_diags = _git_ls_files_index(repo, limits, deadline, env=git_env)
            diagnostics.extend(list_diags)
            for rel, mode, blob_oid in index_entries:
                tree_entries[rel] = (mode, blob_oid)
        else:
            paths, list_diags = _git_tracked_paths(
                repo,
                limits,
                deadline,
                include_untracked=include_untracked,
                env=git_env,
            )
            diagnostics.extend(list_diags)
            if len(paths) > limits.max_tracked_entries:
                diagnostics.append(
                    Diagnostic(
                        code="LIMIT_EXCEEDED",
                        message="Tracked paths exceed max_tracked_entries",
                        cause="max_tracked_entries_exceeded",
                    )
                )

            for rel in sorted(set(paths)):
                if deadline.is_work_exhausted():
                    diagnostics.append(
                        Diagnostic(code="DEADLINE", message="Capture deadline exhausted", cause="deadline_exceeded")
                    )
                    break

                full_path = repo / rel
                if not full_path.exists():
                    continue

                content, diag, saw_race = _read_bounded_file(full_path, limits)
                if saw_race:
                    race = True
                if diag is not None:
                    diagnostics.append(diag)
                    if diag.cause == "capture_race":
                        race = True
                    continue
                if content is None:
                    continue

                blob_oid = _git_hash_object_w(repo, content, deadline, limits, env=git_env)
                if blob_oid is None:
                    diagnostics.append(
                        Diagnostic(
                            code="BLOB_WRITE",
                            message=f"Failed to write blob for {rel}",
                            path=rel,
                            cause="git_hash_object",
                        )
                    )
                    continue
                tree_entries[rel] = ("100644", blob_oid)

        discovery_complete = not race and not any(
            d.cause in ("capture_race", "git_error", "deadline_exceeded", "max_tracked_entries_exceeded")
            for d in diagnostics
        )

        tree_oid = _EMPTY_TREE_OID
        if tree_entries:
            if discovery_complete:
                built = _build_tree_oid(repo, tree_entries, deadline, limits, env=git_env)
                if built is None:
                    diagnostics.append(
                        Diagnostic(code="TREE_BUILD", message="Failed to build snapshot tree", cause="mktree_failed")
                    )
                    discovery_complete = False
                else:
                    tree_oid = built
            else:
                tree_oid = ""

    manifest = _manifest_digest(tree_entries) if tree_entries else hashlib.sha256(b"").hexdigest()

    return LocalSnapshot(
        tree_oid=tree_oid,
        base_tip=base_tip,
        manifest_digest=manifest,
        capture_mode=capture_mode,
        include_untracked=include_untracked,
        discovery_complete=discovery_complete,
        diagnostics=tuple(diagnostics),
    )


def resolve_repo_git_dir(repo: Path, deadline: Deadline, limits: Limits) -> Path:
    """Resolve the Git directory for a repository or linked worktree."""
    env = _git_env()
    bounds = ProcessBounds(max_stdout_bytes=4096, max_stderr_bytes=limits.max_stderr_bytes, timeout_seconds=5.0)
    cmd = tuple(_safe_git_args(repo) + ["rev-parse", "--git-dir"])
    res = run_bounded(cmd, cwd=repo, env=env, deadline=deadline, bounds=bounds)
    if res.returncode != 0:
        raise ValueError("Failed to resolve git dir")
    git_dir = Path(res.stdout.decode("utf-8").strip())
    if not git_dir.is_absolute():
        git_dir = (repo / git_dir).resolve()
    return git_dir
