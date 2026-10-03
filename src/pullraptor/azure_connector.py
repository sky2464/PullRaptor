"""Bounded Azure DevOps review acquisition with injectable fake transport (E09-T1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any, Protocol

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class TransportPolicy:
    """Bounded transport rules from E09-D1."""

    max_response_bytes: int = 1_048_576
    allow_live_network: bool = False


@dataclass(frozen=True)
class AzureConnectorPolicy:
    organization_id: str
    allowed_repository_ids: frozenset[str]
    api_version: str
    transport_policy: TransportPolicy


@dataclass(frozen=True)
class ConnectorCredentials:
    credential_id: str
    organization_id: str
    scopes: frozenset[str]
    expires_at: float


@dataclass(frozen=True)
class AzureEventHint:
    """Untrusted delivery/event metadata; never grants repository or ref authority."""

    organization_id: str | None = None
    repository_id: str | None = None
    source_head: str | None = None
    target_ref: str | None = None
    iteration_id: int | None = None


@dataclass(frozen=True)
class AzureReviewContext:
    platform: str
    organization_id: str
    project_id: str
    repository_id: str
    pr_id: int
    iteration_id: int
    source_head: str
    target_tip: str
    comparison_base: str
    policy_digest: str
    scope_digest: str
    reviewer_digest: str


@dataclass(frozen=True)
class AzureAcquisition:
    status: str
    context: AzureReviewContext | None
    acquired_source_bytes: int
    cause: str


@dataclass(frozen=True)
class AzureRequestDescriptor:
    operation: str
    organization_id: str
    project_id: str
    repository_id: str
    pr_id: int
    iteration_id: int | None = None


class AzureTransport(Protocol):
    def send_descriptor(self, descriptor: AzureRequestDescriptor) -> tuple[int, bytes]:
        """Return HTTP-like status and bounded response body."""


@dataclass
class FakeAzureTransport:
    """Recorded responses keyed by operation and coordinates."""

    fixtures: dict[tuple[str, str, str, int, int | None], tuple[int, dict[str, Any]]]
    sent: list[AzureRequestDescriptor]
    acquired_source_bytes: int = 0

    def send_descriptor(self, descriptor: AzureRequestDescriptor) -> tuple[int, bytes]:
        self.sent.append(descriptor)
        key = (
            descriptor.operation,
            descriptor.organization_id,
            descriptor.repository_id,
            descriptor.pr_id,
            descriptor.iteration_id,
        )
        status, payload = self.fixtures.get(key, (404, {"error": "not_found"}))
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if status == 200:
            self.acquired_source_bytes += len(body)
        return status, body[:1_048_576]


def _digest(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _valid_head(value: str) -> bool:
    return bool(_SHA_RE.match(value))


def _credentials_ok(credentials: ConnectorCredentials, policy: AzureConnectorPolicy, now: float) -> str | None:
    if now >= credentials.expires_at:
        return "credentials_expired"
    if credentials.organization_id != policy.organization_id:
        return "wrong_organization"
    required = frozenset({"vso.code"})
    if not required.issubset(credentials.scopes):
        return "insufficient_scope"
    return None


def _parse_iteration_payload(payload: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    source = payload["source_head"]
    target = payload["target_tip"]
    base = payload["comparison_base"]
    policy_digest = payload["policy_digest"]
    scope_digest = payload["scope_digest"]
    reviewer_digest = payload["reviewer_digest"]
    for value in (source, target, base):
        if not _valid_head(value):
            raise ValueError("invalid_head_in_fixture")
    return source, target, base, policy_digest, scope_digest, reviewer_digest


def resolve_azure_review(
    pr_id: int,
    *,
    connector: AzureConnectorPolicy,
    credentials: ConnectorCredentials,
    transport: AzureTransport,
    project_id: str,
    repository_id: str,
    iteration_id: int,
    event_hint: AzureEventHint | None = None,
    prior_context: AzureReviewContext | None = None,
    now: float | None = None,
) -> AzureAcquisition:
    """Acquire immutable PR iteration context using scoped policy and fake transport."""
    clock = time.time() if now is None else now
    acquired = 0

    if connector.transport_policy.allow_live_network:
        return AzureAcquisition("unavailable", None, 0, "live_network_not_admitted")

    cred_cause = _credentials_ok(credentials, connector, clock)
    if cred_cause is not None:
        return AzureAcquisition("unavailable", None, 0, cred_cause)

    if repository_id not in connector.allowed_repository_ids:
        return AzureAcquisition("denied", None, 0, "repository_not_allowlisted")

    if event_hint is not None:
        if event_hint.organization_id and event_hint.organization_id != connector.organization_id:
            return AzureAcquisition("denied", None, 0, "event_org_not_authoritative")
        if event_hint.repository_id and event_hint.repository_id != repository_id:
            return AzureAcquisition("denied", None, 0, "event_repository_not_authoritative")
        if event_hint.source_head and not _valid_head(event_hint.source_head):
            return AzureAcquisition("denied", None, 0, "event_ref_not_authoritative")

    descriptor = AzureRequestDescriptor(
        operation="get_pull_request_iteration",
        organization_id=connector.organization_id,
        project_id=project_id,
        repository_id=repository_id,
        pr_id=pr_id,
        iteration_id=iteration_id,
    )
    status, body = transport.send_descriptor(descriptor)
    if hasattr(transport, "acquired_source_bytes"):
        acquired = getattr(transport, "acquired_source_bytes")
    if status != 200:
        return AzureAcquisition("denied", None, acquired, "platform_denied")

    payload = json.loads(body.decode("utf-8"))
    if payload.get("iteration_id") != iteration_id:
        return AzureAcquisition("denied", None, acquired, "iteration_mismatch")

    try:
        source, target, base, policy_digest, scope_digest, reviewer_digest = _parse_iteration_payload(payload)
    except (KeyError, ValueError):
        return AzureAcquisition("denied", None, acquired, "invalid_platform_payload")

    context = AzureReviewContext(
        platform="azure_devops_services",
        organization_id=connector.organization_id,
        project_id=project_id,
        repository_id=repository_id,
        pr_id=pr_id,
        iteration_id=iteration_id,
        source_head=source,
        target_tip=target,
        comparison_base=base,
        policy_digest=policy_digest,
        scope_digest=scope_digest,
        reviewer_digest=reviewer_digest,
    )

    if prior_context is not None:
        if (
            prior_context.source_head == context.source_head
            and prior_context.policy_digest != context.policy_digest
        ):
            return AzureAcquisition("stale", context, acquired, "target_policy_drift")

    if event_hint is not None and event_hint.iteration_id is not None:
        if event_hint.iteration_id != iteration_id:
            return AzureAcquisition("denied", None, acquired, "event_iteration_not_authoritative")

    return AzureAcquisition("ok", context, acquired, "ok")


def scope_digest_from_paths(paths: tuple[str, ...]) -> str:
    return _digest(tuple(sorted(paths)))
