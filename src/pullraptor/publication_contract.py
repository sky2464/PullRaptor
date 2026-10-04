"""Independent publication authorization against platform-derived context."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from pullraptor.evidence import validate_receipts
from pullraptor.models import Finding, FullReport, LimitFailure, Report, ScopeEntry

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


def scope_digest_from_scope(entries: tuple[ScopeEntry, ...]) -> str:
    """Stable digest over every coordinator scope field, not path names alone."""
    lines: list[str] = []
    for entry in sorted(entries, key=lambda item: item.key):
        path_bytes = entry.path_bytes.hex() if entry.path_bytes is not None else ""
        relative = "" if entry.relative_level is None else str(entry.relative_level)
        lines.append(
            "|".join(
                (
                    entry.key,
                    entry.kind,
                    entry.snapshot,
                    entry.capability,
                    path_bytes,
                    entry.path or "",
                    entry.source_occurrence or "",
                    entry.canonical_target or "",
                    relative,
                    entry.reason,
                )
            )
        )
    joined = "\n".join(lines)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def scope_digest_from_report(report: FullReport) -> str:
    """Derive a stable scope digest from the report contract."""
    return scope_digest_from_scope(report.contract.expected_scope)


def _inline_keys_for_findings(findings: tuple[Finding, ...], inventory: tuple[str, ...]) -> tuple[str, ...]:
    admitted = set(inventory)
    keys: list[str] = []
    for finding in findings:
        path = finding.span.path
        if path not in admitted:
            continue
        if finding.span.side != "head":
            continue
        keys.append(f"{finding.obligation}:{finding.anchor}")
    return tuple(sorted(keys)[:10])


def _report_contract_matches_context(report: FullReport, expected: PublicationContext) -> str | None:
    contract = report.contract
    if contract.head != expected.head:
        return "report_contract_context_mismatch"
    if contract.base_tip != expected.base_tip:
        return "report_contract_context_mismatch"
    if contract.comparison_base != expected.comparison_base:
        return "report_contract_context_mismatch"
    if contract.policy_digest != expected.policy_digest:
        return "report_contract_context_mismatch"
    computed_scope = scope_digest_from_report(report)
    if computed_scope != expected.scope_digest:
        return "scope_capability_revision_collision"
    return None


def _finding_inline_eligible(finding: Finding, inventory: set[str]) -> str | None:
    if finding.span.path not in inventory:
        return "deleted_side_location"
    if finding.span.side != "head":
        return "invalid_side_location"
    return None


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

    if current.head == expected.head and current.policy_digest != expected.policy_digest:
        return PublicationDecision(authorized=False, cause="stale_policy", inline_keys=())

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
        if "scope_digest" in mismatched:
            return PublicationDecision(authorized=False, cause="scope_capability_revision_collision", inline_keys=())
        return PublicationDecision(authorized=False, cause="context_mismatch", inline_keys=())

    assert isinstance(report, FullReport)

    contract_mismatch = _report_contract_matches_context(report, expected)
    if contract_mismatch is not None:
        return PublicationDecision(authorized=False, cause=contract_mismatch, inline_keys=())

    receipt_diagnostics = validate_receipts(report.contract, report.receipts)
    if receipt_diagnostics or not report.contract.discovery_complete:
        return PublicationDecision(authorized=False, cause="incomplete_receipts", inline_keys=())

    inventory = set(report.inventory)
    for finding in report.findings:
        location_issue = _finding_inline_eligible(finding, inventory)
        if location_issue is not None:
            return PublicationDecision(authorized=False, cause=location_issue, inline_keys=())

    inline_keys = _inline_keys_for_findings(report.findings, report.inventory)
    return PublicationDecision(authorized=True, cause="authorized", inline_keys=inline_keys)
