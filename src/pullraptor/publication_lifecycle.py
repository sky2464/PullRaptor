"""Revision-bound comment lifecycle planning with duplicate-safe reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from pullraptor.models import FullReport, Report


@dataclass(frozen=True)
class PublishedObservation:
    """Connector-owned observation of a published review obligation."""

    owner_id: str
    platform_id: str
    obligation_key: str
    observation_id: str
    witness_digest: str
    dismissed: bool


@dataclass(frozen=True)
class PublicationPlan:
    """Bounded publication actions for one reconciliation pass."""

    create: tuple[str, ...]
    update: tuple[str, ...]
    outdated: tuple[str, ...]
    deferred: tuple[str, ...]


_BOT_OWNER = "pullraptor-bot"
_INLINE_CAP = 10


def _witness_digest(witness: str) -> str:
    return hashlib.sha256(witness.encode("utf-8")).hexdigest()


def _obligation_key(finding) -> str:
    return f"{finding.obligation}:{finding.anchor}"


def plan_publication(
    context_artifact_digest: str,
    report: Report,
    existing: tuple[PublishedObservation, ...],
) -> PublicationPlan:
    """Plan create/update/outdated actions without blind duplicate writes."""
    if report.kind != "full":
        return PublicationPlan(create=(), update=(), outdated=(), deferred=())

    assert isinstance(report, FullReport)
    owned = [obs for obs in existing if obs.owner_id == _BOT_OWNER]
    owned_by_key = {obs.obligation_key: obs for obs in owned}

    create: list[str] = []
    update: list[str] = []
    outdated: list[str] = []
    deferred: list[str] = []

    findings = list(report.findings)
    if len(findings) > _INLINE_CAP:
        deferred.extend(_obligation_key(f) for f in findings[_INLINE_CAP:])

    for finding in findings[:_INLINE_CAP]:
        key = _obligation_key(finding)
        witness = _witness_digest(finding.witness)
        prior = owned_by_key.get(key)
        if prior is None:
            create.append(key)
            continue
        if prior.dismissed:
            deferred.append(key)
            continue
        if prior.witness_digest != witness:
            update.append(prior.observation_id)
            continue
        if prior.platform_id and prior.observation_id:
            continue

    for obs in owned:
        if obs.obligation_key not in {_obligation_key(f) for f in findings[:_INLINE_CAP]}:
            outdated.append(obs.observation_id)

    reconciled_create = tuple(create)
    if context_artifact_digest and owned and not create and not update:
        reconciled_create = ()

    return PublicationPlan(
        create=reconciled_create,
        update=tuple(update),
        outdated=tuple(outdated),
        deferred=tuple(deferred),
    )
