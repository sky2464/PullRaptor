"""Publication authorization against a trusted, independently frozen authority."""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import re

from pullraptor.evidence import validate_receipts
from pullraptor.models import Finding, FullReport, LimitFailure, Report, ScopeEntry

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class PublicationRange:
    """Connector-admitted current diff lines; never obtained from report inventory."""
    path: str
    side: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class PublicationContext:
    """Trusted authority, not a report envelope or user-supplied identity assertion.

    The connector pins platform origin and artifact/reviewer SHA-256 independently;
    tool_digest is the expected semantic tool identifier (not reviewer bytes).
    policy/config/profile/scope come from the trusted coordinator contract, and
    report_digest pins the exact downloaded report bytes. A fresh connector reads
    all these identities and permitted diff ranges before each write attempt.
    Empty defaults preserve construction compatibility but never authorize.
    """
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
    config_digest: str = ""
    tool_digest: str = ""
    profile: str = ""
    report_digest: str = ""
    permitted_ranges: tuple[PublicationRange, ...] = ()
    object_format: str = "sha1"


@dataclass(frozen=True)
class PublicationDecision:
    authorized: bool
    cause: str
    inline_keys: tuple[str, ...]


def scope_digest_from_scope(entries: tuple[ScopeEntry, ...]) -> str:
    """Versioned canonical JSON; preserves null/empty and escapes separators."""
    records = []
    for entry in entries:
        record = {field.name: getattr(entry, field.name) for field in fields(ScopeEntry)}
        record['path_bytes'] = entry.path_bytes.hex() if entry.path_bytes is not None else None
        records.append(record)
    # Sort complete records, including ties; receipt validation rejects duplicate keys.
    encoded = sorted(json.dumps(record, sort_keys=True, ensure_ascii=True,
                                separators=(',', ':')) for record in records)
    raw = json.dumps({'schema': 'pullraptor.publication-scope/2', 'entries': encoded},
                     sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def scope_digest_from_report(report: FullReport) -> str:
    return scope_digest_from_scope(report.contract.expected_scope)


def _context_issue(context: PublicationContext) -> str | None:
    width = {'sha1': 40, 'sha256': 64}.get(context.object_format)
    if width is None:
        return 'invalid_object_format'
    for name in ('head', 'base_tip', 'comparison_base'):
        value = getattr(context, name)
        if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{' + str(width) + r'}', value) is None:
            return 'invalid_' + name
    for name in ('repository_id', 'workflow_id', 'run_id', 'policy_digest', 'config_digest',
                 'tool_digest', 'profile'):
        value = getattr(context, name)
        if not isinstance(value, str) or not value.strip():
            return 'invalid_identity:' + name
    if type(context.pr_number) is not int or context.pr_number < 1:
        return 'invalid_identity:pr_number'
    for name in ('artifact_digest', 'reviewer_digest', 'report_digest', 'scope_digest'):
        value = getattr(context, name)
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            return 'invalid_digest:' + name
    if not isinstance(context.permitted_ranges, tuple):
        return 'invalid_diff_ranges'
    for item in context.permitted_ranges:
        if (not isinstance(item, PublicationRange) or not isinstance(item.path, str)
                or not item.path or item.side != 'head'
                or type(item.start_line) is not int or type(item.end_line) is not int
                or item.start_line < 1 or item.end_line < item.start_line):
            return 'invalid_diff_ranges'
    return None


def _report_contract_matches_context(report: FullReport, expected: PublicationContext) -> str | None:
    for name in ('head', 'base_tip', 'comparison_base', 'policy_digest', 'config_digest',
                 'tool_digest', 'profile'):
        if getattr(report.contract, name) != getattr(expected, name):
            return 'report_contract_context_mismatch'
    if scope_digest_from_report(report) != expected.scope_digest:
        return 'scope_capability_revision_collision'
    return None


def _finding_issue(finding: Finding, inventory: set[str], ranges: tuple[PublicationRange, ...]) -> str | None:
    span = finding.span
    if span.path not in inventory:
        return 'deleted_side_location'
    if span.side != 'head':
        return 'invalid_side_location'
    if type(span.start_line) is not int or type(span.end_line) is not int or span.start_line < 1 or span.end_line < span.start_line:
        return 'invalid_line_location'
    if not any(item.path == span.path and item.side == span.side
               and item.start_line <= span.start_line <= span.end_line <= item.end_line for item in ranges):
        return 'out_of_diff_location'
    return None


def validate_publication(report: Report, expected: PublicationContext, current: PublicationContext,
                         *, actual_report_digest: str | None = None) -> PublicationDecision:
    """Pure gate; actual_report_digest must be recomputed from the downloaded bytes."""
    def deny(cause: str) -> PublicationDecision:
        return PublicationDecision(False, cause, ())
    if isinstance(report, LimitFailure):
        return deny('limit_failure')
    if not isinstance(expected, PublicationContext) or not isinstance(current, PublicationContext):
        return deny('missing_publication_authority')
    for context in (expected, current):
        issue = _context_issue(context)
        if issue:
            return deny(issue)
    if actual_report_digest != expected.report_digest:
        return deny('report_bytes_mismatch')
    mismatched = [field.name for field in fields(PublicationContext)
                  if getattr(expected, field.name) != getattr(current, field.name)]
    if mismatched:
        if 'pr_number' in mismatched:
            return deny('cross_pr_replay')
        if any(name in mismatched for name in ('workflow_id', 'run_id', 'artifact_digest')):
            return deny('wrong_workflow_run_artifact')
        if 'policy_digest' in mismatched:
            return deny('stale_policy')
        if 'head' in mismatched:
            return deny('stale_head')
        if 'scope_digest' in mismatched:
            return deny('scope_capability_revision_collision')
        return deny('context_mismatch')
    issue = _report_contract_matches_context(report, expected)
    if issue:
        return deny(issue)
    scope_keys = tuple(entry.key for entry in report.contract.expected_scope)
    if (len(set(scope_keys)) != len(scope_keys)
            or any(receipt.status != "complete" for receipt in report.receipts)
            or validate_receipts(report.contract, report.receipts)
            or report.contract.discovery_complete is not True):
        return deny('incomplete_receipts')
    for finding in report.findings:
        issue = _finding_issue(finding, set(report.inventory), current.permitted_ranges)
        if issue:
            return deny(issue)
    keys = tuple(sorted(f'{finding.obligation}:{finding.anchor}' for finding in report.findings)[:10])
    return PublicationDecision(True, 'authorized', keys)
