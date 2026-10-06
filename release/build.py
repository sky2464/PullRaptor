"""Release candidate builder and manifest producer (E07; not product acceptance)."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pullraptor.release_provenance import (  # noqa: E402
    BuildOrigin,
    ReleaseManifest,
    artifact_identity_from_bytes,
    dependency_inventory_from_inventory_doc,
    dump_manifest,
    entrypoints_from_inventory_doc,
    load_build_origin_from_environ,
    manifest_from_dict,
    provenance_ref_from_origin,
    runtime_matrix_from_inventory_doc,
    validate_source_revision,
    verify_release,
)

__all__ = (
    "BuildOrigin",
    "ReleaseManifest",
    "dump_manifest",
    "load_build_origin_from_environ",
    "main",
    "manifest_from_dict",
    "produce_release_candidate",
    "verify_release",
)

BUILDER_COMMAND = "PYTHONPATH=src python3.12 release/build.py"


def _wheel_python() -> str:
    if sys.version_info[:2] == (3, 12):
        return sys.executable
    candidate = shutil.which("python3.12")
    if candidate:
        return candidate
    raise RuntimeError("python_3.12_required_for_wheel_build")


def _assert_revision_exists(repo_root: Path, revision: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{revision}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("source_revision_not_found_in_repository")


def _build_wheel_bytes(repo_root: Path, source_revision: str) -> bytes:
    """Build wheel bytes from an exact committed tree (git archive), not the working copy."""
    _assert_revision_exists(repo_root, source_revision)
    wheel_python = _wheel_python()
    with tempfile.TemporaryDirectory(prefix="pullraptor-release-archive-") as tmp:
        extract_root = Path(tmp) / "tree"
        extract_root.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(repo_root), "archive", "--format=tar", source_revision],
            check=False,
            capture_output=True,
        )
        if archive.returncode != 0:
            raise RuntimeError(archive.stderr.decode("utf-8", errors="replace") or "git_archive_failed")
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
            tar.extractall(extract_root, filter="data")
        staging = Path(tmp) / "wheels"
        staging.mkdir()
        env = os.environ.copy()
        env.setdefault("SOURCE_DATE_EPOCH", "0")
        result = subprocess.run(
            [
                wheel_python,
                "-m",
                "pip",
                "wheel",
                str(extract_root),
                "--no-deps",
                "-w",
                str(staging),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "wheel_build_failed")
        wheels = sorted(staging.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("expected_exactly_one_wheel")
        return wheels[0].read_bytes()


def _read_inventory(repo_root: Path) -> dict:
    path = repo_root / "docs" / "dependencies" / "E07.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _project_version(repo_root: Path, source_revision: str) -> str:
    shown = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{source_revision}:pyproject.toml"],
        capture_output=True,
        text=True,
    )
    if shown.returncode != 0:
        pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
        return str(pyproject["project"]["version"])
    pyproject = tomllib.loads(shown.stdout)
    return str(pyproject["project"]["version"])


def _resolve_source_revision(repo_root: Path, explicit: str | None) -> str:
    revision = explicit
    if not revision:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError("unable_to_resolve_source_revision")
        revision = result.stdout.strip()
    validate_source_revision(revision)
    return revision


def produce_release_candidate(
    repo_root: Path,
    output_dir: Path,
    *,
    source_revision: str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[ReleaseManifest, BuildOrigin, dict[str, bytes]]:
    """Build wheel artifact bytes and emit a candidate manifest (not public release acceptance)."""
    revision = _resolve_source_revision(repo_root, source_revision)
    inventory = _read_inventory(repo_root)
    wheel_bytes = _build_wheel_bytes(repo_root, revision)
    entrypoints = entrypoints_from_inventory_doc(inventory)
    wheel = artifact_identity_from_bytes("wheel", wheel_bytes, entrypoints=entrypoints)
    origin = load_build_origin_from_environ((wheel.digest,), environ=environ)
    manifest = ReleaseManifest(
        version=_project_version(repo_root, revision),
        source_revision=revision,
        artifacts=(wheel,),
        runtime_matrix=runtime_matrix_from_inventory_doc(inventory),
        dependency_inventory=dependency_inventory_from_inventory_doc(inventory),
        provenance_ref=provenance_ref_from_origin(origin),
    )
    decision = verify_release(
        manifest,
        revision,
        origin,
        artifact_bytes={wheel.digest: wheel_bytes},
    )
    if not decision.admitted:
        raise RuntimeError(f"manifest_self_check_failed:{decision.cause}")
    output_dir.mkdir(parents=True, exist_ok=True)
    dump_manifest(manifest, output_dir / "manifest.json")
    receipt = {
        "builder_command": BUILDER_COMMAND,
        "build_method": "git_archive_exact_revision",
        "candidate_only": True,
        "product_acceptance": "pending",
        "source_revision": revision,
        "workflow_digest": origin.workflow_digest,
        "run_id": origin.run_id,
        "repository_id": origin.repository_id,
        "artifact_digests": list(origin.artifact_digests),
        "manifest_path": "manifest.json",
    }
    (output_dir / "build-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / f"pullraptor-{manifest.version}-py3-none-any.whl").write_bytes(wheel_bytes)
    return manifest, origin, {wheel.digest: wheel_bytes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a release candidate wheel and manifest (E07 candidate; not accepted release).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "build" / "release-candidate",
        help="Directory for manifest, receipt, and wheel bytes",
    )
    parser.add_argument(
        "--source-revision",
        help="40-character git commit hash; defaults to git rev-parse HEAD",
    )
    args = parser.parse_args(argv)
    try:
        produce_release_candidate(
            _REPO_ROOT,
            args.output_dir,
            source_revision=args.source_revision,
        )
    except (ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"release candidate build failed: {exc}", file=sys.stderr)
        return 1
    print(
        "release candidate manifest written; product acceptance remains pending "
        f"under {args.output_dir}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
