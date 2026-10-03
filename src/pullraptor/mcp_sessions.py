"""Bounded MCP session state and report identity (E08-A1 construction)."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from pullraptor.models import FullReport, Report, canonical_bytes, RecordLimits, Deadline
import time

PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = frozenset({PROTOCOL_VERSION})

MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 8_388_608
MAX_JSON_DEPTH = 64
MAX_JSON_ITEMS = 10_000
MAX_REVIEWS_PER_SESSION = 2
MAX_REPORTS_PER_SESSION = 10
MAX_REPORT_BYTES_TOTAL = 64 * 1_048_576


@dataclass(frozen=True)
class SessionReport:
    """Pinned report visible within one authorized session."""

    session_id: str
    authorized_repository_id: str
    report_digest: str
    head_or_snapshot: str
    context_digest: str
    report: Report
    freshness: str


@dataclass
class MCPSession:
    """Operator-scoped MCP session with explicit report retention."""

    id: str
    workspace_grants: frozenset[str]
    negotiated_version: str | None = None
    reports: dict[str, SessionReport] = field(default_factory=dict)
    active_reviews: int = 0
    report_bytes_total: int = 0
    initialized: bool = False


def report_digest_for(report: Report, *, limits: RecordLimits, deadline: Deadline) -> str:
    payload = canonical_bytes(report, limits=limits, deadline=deadline)
    return hashlib.sha256(payload).hexdigest()


def context_digest_for(repository_id: str, head_or_snapshot: str) -> str:
    material = f"{repository_id}\0{head_or_snapshot}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def register_session_report(
    session: MCPSession,
    *,
    authorized_repository_id: str,
    report: Report,
    head_or_snapshot: str,
    limits: RecordLimits,
    deadline: Deadline,
    freshness: str = "current",
) -> SessionReport:
    """Store a report under an explicit digest key with bounded retention."""
    digest = report_digest_for(report, limits=limits, deadline=deadline)
    ctx = context_digest_for(authorized_repository_id, head_or_snapshot)
    size = len(canonical_bytes(report, limits=limits, deadline=deadline))
    if digest not in session.reports:
        if len(session.reports) >= MAX_REPORTS_PER_SESSION:
            oldest = next(iter(session.reports))
            removed = session.reports.pop(oldest)
            session.report_bytes_total -= len(
                canonical_bytes(removed.report, limits=limits, deadline=deadline)
            )
        session.report_bytes_total += size
    entry = SessionReport(
        session_id=session.id,
        authorized_repository_id=authorized_repository_id,
        report_digest=digest,
        head_or_snapshot=head_or_snapshot,
        context_digest=ctx,
        report=report,
        freshness=freshness,
    )
    session.reports[digest] = entry
    return entry


def get_session_report(
    session_id: str,
    report_digest: str,
    authorized_repository_id: str,
    *,
    session: MCPSession,
) -> SessionReport | None:
    """Lookup a pinned report; deny cross-repository access."""
    if session.id != session_id:
        return None
    entry = session.reports.get(report_digest)
    if entry is None:
        return None
    if entry.authorized_repository_id != authorized_repository_id:
        return None
    return entry


def evict_report(session: MCPSession, report_digest: str, *, limits: RecordLimits, deadline: Deadline) -> bool:
    """Explicitly evict one report digest from the session."""
    entry = session.reports.pop(report_digest, None)
    if entry is None:
        return False
    session.report_bytes_total -= len(canonical_bytes(entry.report, limits=limits, deadline=deadline))
    return True


def _json_depth(value: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        if not value:
            return depth
        return max(_json_depth(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_json_depth(v, depth + 1) for v in value)
    return depth


def _json_item_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_json_item_count(v) for v in value.values())
    if isinstance(value, list):
        return len(value) + sum(_json_item_count(v) for v in value)
    return 1


def validate_request_bytes(payload: bytes) -> str | None:
    if len(payload) > MAX_REQUEST_BYTES:
        return "oversized_request"
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid_json"
    if _json_depth(decoded) > MAX_JSON_DEPTH:
        return "depth_exceeded"
    if _json_item_count(decoded) > MAX_JSON_ITEMS:
        return "item_cap_exceeded"
    if isinstance(decoded, dict):
        keys = list(decoded.keys())
        if len(keys) != len(set(keys)):
            return "duplicate_keys"
        for key in decoded:
            if not isinstance(key, str):
                return "invalid_key_type"
    return None


def negotiate_protocol_version(requested: str | None) -> tuple[str | None, str | None]:
    if requested is None:
        return None, "version_required"
    if requested not in SUPPORTED_PROTOCOL_VERSIONS:
        return None, "version_unsupported"
    return requested, None


def reject_unknown_fields(params: dict[str, Any], allowed: frozenset[str]) -> str | None:
    extra = set(params) - set(allowed)
    if extra:
        return "unknown_fields"
    return None


def default_deadline() -> Deadline:
    return Deadline(started_at=time.monotonic(), duration_seconds=10.0)
