"""Independent publication authorization against platform-derived context."""

from __future__ import annotations

from dataclasses import dataclass
import re

from pullraptor.models import Finding, FullReport, LimitFailure, Report

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class PublicationContext:
    """Connector-owned publication binding derived from the platform."""

    repository_id: str
    pr_number: int
    workflow_id: str
    run_id: str
    artifact_digest: str
    reviewer_digest: str
    head: str
    base_tip: str
    comparison_base: str
    policy_digest: str
    scope_digest: str


@dataclass(frozen=True)
class PublicationDecision:
    """Authorization outcome for a publication attempt."""

    authorized: bool
    cause: str
    inline_keys: tuple[str, ...]


def _valid_head(head: str) -> bool:
    return bool(_FULL_SHA_RE.match(head))


def _inline_keys_for_findings(findings: tuple[Finding, ...], inventory: tuple[str, ...]) -> tuple[str, ...]:
    admitted = set(inventory)
    keys: list[str] = []
    for finding in findings:
        path = finding.span.path
        if path not in admitted:
            continue
        keys.append(f"{finding.obligation}:{finding.anchor}")
    return tuple(sorted(keys)[:10])


def validate_publication(
    report: Report,
    expected: PublicationContext,
    current: PublicationContext,
) -> PublicationDecision:
    """Validate that the current platform context authorizes publishing the pinned report."""
    if isinstance(report, LimitFailure):
        return PublicationDecision(authorized=False, cause="limit_failure", inline_keys=())

    if not _valid_head(expected.head) or not _valid_head(current.head):
        return PublicationDecision(authorized=False, cause="invalid_head", inline_keys=())

    identity_fields = (
        "repository_id",
        "pr_number",
        "workflow_id",
        "run_id",
        "artifact_digest",
        "reviewer_digest",
        "head",
        "base_tip",
        "comparison_base",
        "policy_digest",
        "scope_digest",
    )

    if current.head == expected.head and current.policy_digest != expected.policy_digest:
        return PublicationDecision(authorized=False, cause="stale_policy", inline_keys=())

    mismatched = [field for field in identity_fields if getattr(current, field) != getattr(expected, field)]
    if mismatched:
        if "pr_number" in mismatched:
            return PublicationDecision(authorized=False, cause="cross_pr_replay", inline_keys=())
        if any(name in mismatched for name in ("workflow_id", "run_id", "artifact_digest")):
            return PublicationDecision(authorized=False, cause="wrong_workflow_run_artifact", inline_keys=())
        if "policy_digest" in mismatched:
            return PublicationDecision(authorized=False, cause="stale_policy", inline_keys=())
        if "head" in mismatched:
            return PublicationDecision(authorized=False, cause="stale_head", inline_keys=())
        return PublicationDecision(authorized=False, cause="context_mismatch", inline_keys=())

    assert isinstance(report, FullReport)
    inventory = set(report.inventory)
    for finding in report.findings:
        if finding.span.path not in inventory:
            return PublicationDecision(authorized=False, cause="deleted_side_location", inline_keys=())

    inline_keys = _inline_keys_for_findings(report.findings, report.inventory)
    return PublicationDecision(authorized=True, cause="authorized", inline_keys=inline_keys)


def scope_digest_from_report(report: FullReport) -> str:
    """Derive a stable scope digest from the report contract."""
    parts = [entry.path for entry in report.contract.expected_scope]
    joined = "\n".join(sorted(parts))
    import hashlib

    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
