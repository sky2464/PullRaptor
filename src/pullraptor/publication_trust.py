"""CI publication trust: isolation admission, artifact receipts, and dev CI policy checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PERMISSION_RANK = {"read": 1, "write": 2, "admin": 3, "none": 0}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ArtifactReceipt:
    """Connector-owned binding between a workflow run and a bounded report artifact."""

    repository_id: str
    pr_number: int
    workflow_id: str
    run_id: str
    artifact_digest: str
    reviewer_digest: str


@dataclass(frozen=True)
class ReceiptDecision:
    authorized: bool
    cause: str


@dataclass(frozen=True)
class IsolationControls:
    """Observed deployment controls for disposable analysis (not kernel claims)."""

    egress_denied: bool
    source_readonly: bool
    publisher_credential_absent: bool
    process_isolated: bool


@dataclass(frozen=True)
class AdmissionDecision:
    profile: str
    admission: str
    cause: str


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def receipt_from_mapping(data: dict[str, Any]) -> ArtifactReceipt:
    pr_number = int(data["pr_number"])
    return ArtifactReceipt(
        repository_id=str(data["repository_id"]),
        pr_number=pr_number,
        workflow_id=str(data["workflow_id"]),
        run_id=str(data["run_id"]),
        artifact_digest=str(data["artifact_digest"]),
        reviewer_digest=str(data["reviewer_digest"]),
    )


def validate_artifact_receipt(expected: ArtifactReceipt, actual: ArtifactReceipt) -> ReceiptDecision:
    """Reject cross-run, cross-repo, or tampered artifact origins before publication."""
    if not _SHA256_RE.fullmatch(expected.artifact_digest) or not _SHA256_RE.fullmatch(actual.artifact_digest):
        return ReceiptDecision(authorized=False, cause="invalid_artifact_digest")
    if not _SHA256_RE.fullmatch(expected.reviewer_digest) or not _SHA256_RE.fullmatch(actual.reviewer_digest):
        return ReceiptDecision(authorized=False, cause="invalid_reviewer_digest")

    identity_fields = (
        ("repository_id", expected.repository_id, actual.repository_id),
        ("pr_number", expected.pr_number, actual.pr_number),
        ("workflow_id", expected.workflow_id, actual.workflow_id),
        ("run_id", expected.run_id, actual.run_id),
        ("artifact_digest", expected.artifact_digest, actual.artifact_digest),
        ("reviewer_digest", expected.reviewer_digest, actual.reviewer_digest),
    )
    for name, exp, cur in identity_fields:
        if exp != cur:
            if name == "pr_number":
                return ReceiptDecision(authorized=False, cause="cross_pr_replay")
            if name in ("workflow_id", "run_id", "artifact_digest"):
                return ReceiptDecision(authorized=False, cause="wrong_workflow_run_artifact")
            return ReceiptDecision(authorized=False, cause=f"receipt_mismatch:{name}")
    return ReceiptDecision(authorized=True, cause="authorized")


def probe_isolation_from_environ() -> IsolationControls:
    """Read isolation probe results exported by the workflow boundary."""
    def _flag(name: str) -> bool:
        return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "enforced"}

    publish_secret = os.environ.get("PULLRAPTOR_PUBLISH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    publisher_absent = not publish_secret.strip()
    return IsolationControls(
        egress_denied=_flag("PULLRAPTOR_ISOLATION_EGRESS_DENIED"),
        source_readonly=_flag("PULLRAPTOR_ISOLATION_SOURCE_READONLY"),
        publisher_credential_absent=publisher_absent,
        process_isolated=_flag("PULLRAPTOR_ISOLATION_PROCESS"),
    )


def evaluate_hostile_admission(controls: IsolationControls, *, profile: str = "hostile") -> AdmissionDecision:
    """Fail closed when required disposable controls are not independently enforced."""
    if profile != "hostile":
        return AdmissionDecision(profile=profile, admission="skipped", cause="non_hostile_profile")

    missing: list[str] = []
    if not controls.egress_denied:
        missing.append("egress")
    if not controls.source_readonly:
        missing.append("source_readonly")
    if not controls.publisher_credential_absent:
        missing.append("publisher_credential")
    if not controls.process_isolated:
        missing.append("process")

    if missing:
        return AdmissionDecision(
            profile=profile,
            admission="unavailable",
            cause="missing_controls:" + ",".join(missing),
        )
    return AdmissionDecision(profile=profile, admission="enforced", cause="controls_satisfied")


def refuse_unavailable_hostile(decision: AdmissionDecision) -> int:
    """Exit non-zero when hostile analysis cannot be proven safe."""
    if decision.profile != "hostile":
        return 0
    if decision.admission == "enforced":
        sys.stdout.write(f"PULLRAPTOR_ADMISSION={decision.admission}\n")
        return 0
    sys.stderr.write(
        f"PullRaptor: hostile CI profile refused (admission={decision.admission}; {decision.cause})\n"
    )
    sys.stdout.write(f"PULLRAPTOR_ADMISSION={decision.admission}\n")
    return 1


def _parse_permissions_block(text: str) -> dict[str, str]:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "permissions:":
            start = idx + 1
            break
    if start is None:
        return {}
    perms: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("  ") or line.startswith("    "):
            if perms:
                break
            continue
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        perms[key.strip()] = value.strip()
    return perms


def _permission_weakened(base: str, head: str) -> bool:
    base_rank = _PERMISSION_RANK.get(base, 99)
    head_rank = _PERMISSION_RANK.get(head, 99)
    return head_rank > base_rank


def compare_ci_workflow_policy(base_text: str, head_text: str, *, required_markers: tuple[str, ...]) -> list[str]:
    """Return human-readable violations when head weakens trusted-base development CI policy."""
    violations: list[str] = []

    base_perms = _parse_permissions_block(base_text)
    head_perms = _parse_permissions_block(head_text)
    for key, base_val in base_perms.items():
        if key not in head_perms:
            violations.append(f"removed_permission:{key}")
            continue
        if _permission_weakened(base_val, head_perms[key]):
            violations.append(f"elevated_permission:{key}:{base_val}->{head_perms[key]}")

    for marker in required_markers:
        if marker in base_text and marker not in head_text:
            violations.append(f"removed_required_marker:{marker}")

    if "unittest discover" in base_text and "unittest discover" not in head_text:
        violations.append("removed_unit_test_discovery")

    return violations


def _git_show_file(revision: str, path: str, repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{revision}:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"unable_to_read_trusted_base:{path}")
    return result.stdout


def verify_dev_ci_policy(
    *,
    repo_root: Path,
    base_revision: str,
    head_path: Path,
    workflow_rel: str,
    required_markers: tuple[str, ...],
) -> list[str]:
    base_text = _git_show_file(base_revision, workflow_rel, repo_root)
    head_text = head_path.read_text(encoding="utf-8")
    return compare_ci_workflow_policy(base_text, head_text, required_markers=required_markers)


def write_receipt_json(receipt: ArtifactReceipt, path: Path) -> None:
    payload = {
        "repository_id": receipt.repository_id,
        "pr_number": receipt.pr_number,
        "workflow_id": receipt.workflow_id,
        "run_id": receipt.run_id,
        "artifact_digest": receipt.artifact_digest,
        "reviewer_digest": receipt.reviewer_digest,
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def receipt_from_environ() -> ArtifactReceipt:
    pr_raw = os.environ.get("PULLRAPTOR_PR_NUMBER", "0")
    return ArtifactReceipt(
        repository_id=os.environ.get("PULLRAPTOR_REPOSITORY_ID", os.environ.get("GITHUB_REPOSITORY", "")),
        pr_number=int(pr_raw),
        workflow_id=os.environ.get("PULLRAPTOR_WORKFLOW_ID", os.environ.get("GITHUB_WORKFLOW", "")),
        run_id=os.environ.get("PULLRAPTOR_RUN_ID", os.environ.get("GITHUB_RUN_ID", "")),
        artifact_digest=os.environ.get("PULLRAPTOR_ARTIFACT_DIGEST", ""),
        reviewer_digest=os.environ.get("PULLRAPTOR_REVIEWER_DIGEST", ""),
    )


def _cmd_probe(_args: argparse.Namespace) -> int:
    profile = os.environ.get("PULLRAPTOR_CI_PROFILE", "hostile")
    controls = probe_isolation_from_environ()
    decision = evaluate_hostile_admission(controls, profile=profile)
    return refuse_unavailable_hostile(decision)


def _cmd_validate_receipt(args: argparse.Namespace) -> int:
    expected = receipt_from_mapping(json.loads(Path(args.expected).read_text(encoding="utf-8")))
    actual = receipt_from_environ()
    decision = validate_artifact_receipt(expected, actual)
    if not decision.authorized:
        sys.stderr.write(f"PullRaptor: artifact receipt denied ({decision.cause})\n")
        return 2
    sys.stdout.write("PullRaptor: artifact receipt authorized\n")
    return 0


def _cmd_verify_dev_ci(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve()
    head_path = (repo_root / args.workflow).resolve()
    violations = verify_dev_ci_policy(
        repo_root=repo_root,
        base_revision=args.base,
        head_path=head_path,
        workflow_rel=args.workflow,
        required_markers=tuple(args.required_marker or ()),
    )
    if violations:
        for item in violations:
            sys.stderr.write(f"PullRaptor CI policy: {item}\n")
        return 1
    sys.stdout.write("PullRaptor CI policy: trusted-base constraints satisfied\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pullraptor.publication_trust")
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe-isolation", help="Evaluate hostile CI isolation admission (fail closed)")
    probe.set_defaults(func=_cmd_probe)

    validate = sub.add_parser("validate-receipt", help="Validate artifact receipt against connector environment")
    validate.add_argument("--expected", required=True, help="Path to receipt JSON pinned by the analyze job")
    validate.set_defaults(func=_cmd_validate_receipt)

    verify = sub.add_parser("verify-dev-ci", help="Ensure head workflow does not weaken trusted-base CI policy")
    verify.add_argument("--repo", default=".", help="Repository root")
    verify.add_argument("--base", required=True, help="Trusted base git revision (e.g. merge base SHA)")
    verify.add_argument("--workflow", default=".github/workflows/ci.yml", help="Workflow path relative to repo root")
    verify.add_argument(
        "--required-marker",
        action="append",
        default=[],
        help="Marker substring that must not be removed from the trusted base workflow",
    )
    verify.set_defaults(func=_cmd_verify_dev_ci)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
