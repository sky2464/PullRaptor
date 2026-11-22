"""Revision-bound comment lifecycle planning with duplicate-safe reconciliation.

Stable obligation keys identify a repository, pull request, rule, rule version,
path, qualified obligation, and anchor. Revision observation IDs additionally
pin the head and witness. The planner does not prove bot ownership; the
connector passes the actor id from its authenticated channel.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from pullraptor.models import Finding, FullReport, Report
from pullraptor.publication_contract import PublicationContext


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
    """Bounded publication actions for one reconciliation pass.

    ``create``, ``deferred``, ``ambiguous``, and ``out_of_cap`` carry stable
    obligation keys. ``update`` and ``outdated`` carry platform observation
    IDs. ``renewed`` pairs each previous platform observation ID with the new
    revision observation ID. An ambiguous key stops writes; it is not a
    resolution and it is not an outdated marker.
    """

    create: tuple[str, ...]
    update: tuple[str, ...]
    outdated: tuple[str, ...]
    deferred: tuple[str, ...]
    ambiguous: tuple[str, ...] = ()
    out_of_cap: tuple[str, ...] = ()
    renewed: tuple[tuple[str, str], ...] = ()


INLINE_CAP = 10


def _witness_digest(witness: str) -> str:
    return hashlib.sha256(witness.encode("utf-8")).hexdigest()


def stable_obligation_key(context: PublicationContext, finding: Finding) -> str:
    """Key that survives a new head when the obligation itself is unchanged."""
    payload = {
        "schema": "pullraptor.obligation-key/1",
        "repository_id": context.repository_id,
        "pr_number": context.pr_number,
        "rule": finding.rule,
        "version": finding.version,
        "path": finding.span.path,
        "obligation": finding.obligation,
        "anchor": finding.anchor,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def revision_observation_id(*, obligation_key: str, head: str, witness_digest: str) -> str:
    """Revision-bound observation identity. Distinct from the stable obligation key."""
    payload = {
        "schema": "pullraptor.observation-id/1",
        "obligation_key": obligation_key,
        "head": head,
        "witness_digest": witness_digest,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _empty_plan() -> PublicationPlan:
    return PublicationPlan(create=(), update=(), outdated=(), deferred=())


class InertPublicationConnector:
    """Network-free connector double for lifecycle planning tests."""

    def __init__(
        self,
        context: PublicationContext,
        observations: tuple[PublishedObservation, ...],
        proven_owner_id: str,
    ) -> None:
        self._context = context
        self._observations = tuple(observations)
        self.proven_owner_id = proven_owner_id
        self.write_receipts: list[str] = []

    def current_context(self) -> PublicationContext:
        return self._context

    def list_owned_observations(self) -> tuple[PublishedObservation, ...]:
        if not self.proven_owner_id:
            return ()
        return tuple(
            obs for obs in self._observations if obs.owner_id == self.proven_owner_id
        )

    def plan(self, report: Report) -> PublicationPlan:
        return plan_publication(
            self.current_context(),
            report,
            self._observations,
            proven_owner_id=self.proven_owner_id,
        )

    def write_observation(self, plan: PublicationPlan) -> str:
        receipt = "ambiguous_observation_match" if plan.ambiguous else "accepted"
        self.write_receipts.append(receipt)
        return receipt


def plan_publication(
    context: PublicationContext,
    report: Report,
    existing: tuple[PublishedObservation, ...],
    *,
    proven_owner_id: str,
) -> PublicationPlan:
    """Plan create, update, outdated, and deferred actions without blind duplicates.

    An empty ``proven_owner_id`` means the connector has not proved an owner.
    No observation is then treated as owned, and no create or update is planned.
    Duplicate obligation keys stay in ``ambiguous`` and are neither updated nor
    marked outdated. The inline cap selects the first 10 findings only; later
    findings remain on the plan as out of cap.
    """
    if not isinstance(context, PublicationContext):
        raise TypeError("publication context required")
    if not isinstance(proven_owner_id, str):
        raise TypeError("proven owner id required")
    if not isinstance(report, FullReport) or report.kind != "full":
        return _empty_plan()

    findings = list(report.findings)
    keys = [stable_obligation_key(context, finding) for finding in findings]
    finding_counts: dict[str, int] = {}
    first_finding_keys: list[str] = []
    for key in keys:
        if key not in finding_counts:
            finding_counts[key] = 0
            first_finding_keys.append(key)
        finding_counts[key] += 1

    proved = proven_owner_id != ""
    owned = [obs for obs in existing if proved and obs.owner_id == proven_owner_id]
    groups: dict[str, list[PublishedObservation]] = {}
    for obs in owned:
        groups.setdefault(obs.obligation_key, []).append(obs)

    ambiguous: list[str] = []
    ambiguous_set: set[str] = set()

    def add_ambiguous(key: str) -> None:
        if key not in ambiguous_set:
            ambiguous_set.add(key)
            ambiguous.append(key)

    for key in first_finding_keys:
        if finding_counts[key] > 1:
            add_ambiguous(key)
    for obs in owned:
        if len(groups[obs.obligation_key]) > 1:
            add_ambiguous(obs.obligation_key)

    deferred: list[str] = []
    deferred_set: set[str] = set()
    out_of_cap: list[str] = []
    out_of_cap_set: set[str] = set()

    def defer(key: str) -> None:
        if key in ambiguous_set or key in deferred_set:
            return
        deferred_set.add(key)
        deferred.append(key)

    def mark_out_of_cap(key: str) -> None:
        if key in ambiguous_set or key in out_of_cap_set:
            return
        out_of_cap_set.add(key)
        out_of_cap.append(key)

    for index, key in enumerate(keys):
        if index >= INLINE_CAP:
            mark_out_of_cap(key)

    if not proved:
        for key in keys:
            defer(key)
        return PublicationPlan(
            create=(),
            update=(),
            outdated=(),
            deferred=tuple(deferred),
            ambiguous=tuple(ambiguous),
            out_of_cap=tuple(out_of_cap),
            renewed=(),
        )

    create: list[str] = []
    update: list[str] = []
    renewed: list[tuple[str, str]] = []
    for index, (finding, key) in enumerate(zip(findings, keys)):
        if key in ambiguous_set:
            continue
        if index >= INLINE_CAP:
            defer(key)
            continue
        witness = _witness_digest(finding.witness)
        priors = groups.get(key, [])
        if not priors:
            create.append(key)
            continue
        prior = priors[0]
        if prior.dismissed and prior.witness_digest == witness:
            defer(key)
            continue
        if prior.witness_digest != witness:
            update.append(prior.observation_id)
            renewed.append(
                (
                    prior.observation_id,
                    revision_observation_id(
                        obligation_key=key,
                        head=context.head,
                        witness_digest=witness,
                    ),
                )
            )

    full_keys = set(keys)
    outdated: list[str] = []
    seen_outdated: set[str] = set()
    for obs in owned:
        if obs.obligation_key in ambiguous_set or obs.obligation_key in full_keys:
            continue
        if obs.observation_id in seen_outdated:
            continue
        seen_outdated.add(obs.observation_id)
        outdated.append(obs.observation_id)

    return PublicationPlan(
        create=tuple(create),
        update=tuple(update),
        outdated=tuple(outdated),
        deferred=tuple(deferred),
        ambiguous=tuple(ambiguous),
        out_of_cap=tuple(out_of_cap),
        renewed=tuple(renewed),
    )
