"""Owned local grant evaluation (deny by default; no live identity provider)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from service.contracts import Principal

ROLE_VIEWER = "viewer"
ROLE_REVIEWER = "reviewer"
ROLE_PUBLISHER = "publisher"
ROLE_ADMIN = "admin"

ENTERPRISE_ACTIONS = frozenset(
    {
        "view_report",
        "view_capabilities",
        "read_cache",
        "submit",
        "cancel_own_job",
        "cancel_job",
        "publish",
        "administer_policy",
        "administer_identity",
        "administer_retention",
    }
)

_ACTIONS_BY_ROLE: dict[str, frozenset[str]] = {
    ROLE_VIEWER: frozenset({"view_report", "view_capabilities", "read_cache"}),
    ROLE_REVIEWER: frozenset({"submit", "cancel_own_job"}),
    ROLE_PUBLISHER: frozenset({"publish"}),
    ROLE_ADMIN: frozenset(
        {"administer_policy", "administer_identity", "administer_retention", "cancel_job"}
    ),
}


@dataclass(frozen=True)
class EnterpriseResource:
    tenant_id: str
    kind: str
    resource_id: str
    repository_id: str | None = None
    job_owner_subject_id: str | None = None


@dataclass(frozen=True)
class Membership:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class GrantSnapshot:
    revision: str
    memberships: tuple[Membership, ...]
    revoked_subject_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    cause: str = ""
    grants_revision: str = ""


@dataclass(frozen=True)
class OrganizationPolicyStub:
    """Declarative organization policy record stub for local construction (E11-T2 expands)."""

    revision: str
    issuer: str
    repository_scope: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    retention_days: int = 7


class AuthorizationEvaluator:
    """Evaluate scoped actions against a grant snapshot; default deny."""

    def __init__(self, snapshot: GrantSnapshot) -> None:
        self._snapshot = snapshot

    @property
    def snapshot(self) -> GrantSnapshot:
        return self._snapshot

    def authorize(
        self,
        principal: Principal,
        action: str,
        resource: EnterpriseResource,
    ) -> AccessDecision:
        if action not in ENTERPRISE_ACTIONS:
            return AccessDecision(False, cause="unknown_action", grants_revision=principal.grants_revision)
        if principal.subject_id in self._snapshot.revoked_subject_ids:
            return AccessDecision(False, cause="revoked_principal", grants_revision=self._snapshot.revision)
        if principal.grants_revision != self._snapshot.revision:
            return AccessDecision(False, cause="stale_grants", grants_revision=self._snapshot.revision)
        if resource.tenant_id != principal.tenant_id:
            return AccessDecision(False, cause="tenant_mismatch", grants_revision=self._snapshot.revision)
        roles = self._roles_for(principal)
        if not roles:
            return AccessDecision(False, cause="no_membership", grants_revision=self._snapshot.revision)
        allowed_actions = self._actions_for_roles(roles)
        if action not in allowed_actions:
            return AccessDecision(False, cause="action_denied", grants_revision=self._snapshot.revision)
        if action == "cancel_own_job":
            if resource.job_owner_subject_id != principal.subject_id:
                return AccessDecision(False, cause="not_job_owner", grants_revision=self._snapshot.revision)
        if action in {"view_report", "read_cache", "submit", "cancel_job", "cancel_own_job"}:
            if resource.repository_id is not None and resource.kind == "repository":
                if not self._repository_allowed(roles, resource.repository_id):
                    return AccessDecision(False, cause="repository_denied", grants_revision=self._snapshot.revision)
        return AccessDecision(True, grants_revision=self._snapshot.revision)

    def _roles_for(self, principal: Principal) -> tuple[str, ...]:
        for membership in self._snapshot.memberships:
            if membership.tenant_id == principal.tenant_id and membership.subject_id == principal.subject_id:
                return membership.roles
        return ()

    def _actions_for_roles(self, roles: Sequence[str]) -> frozenset[str]:
        actions: set[str] = set()
        for role in roles:
            actions.update(_ACTIONS_BY_ROLE.get(role, frozenset()))
        return frozenset(actions)

    def _repository_allowed(self, roles: Sequence[str], repository_id: str) -> bool:
        if ROLE_ADMIN in roles:
            return True
        return bool(repository_id)


def authorize(
    principal: Principal,
    action: str,
    resource: EnterpriseResource,
    grants: GrantSnapshot,
) -> AccessDecision:
    return AuthorizationEvaluator(grants).authorize(principal, action, resource)


def membership_for(
    tenant_id: str,
    subject_id: str,
    roles: Sequence[str],
) -> Membership:
    return Membership(tenant_id=tenant_id, subject_id=subject_id, roles=tuple(roles))


def snapshot_from_mapping(
    revision: str,
    memberships: Mapping[tuple[str, str], Sequence[str]],
    revoked: Sequence[str] = (),
) -> GrantSnapshot:
    rows = tuple(
        Membership(tenant_id=tenant, subject_id=subject, roles=tuple(role_list))
        for (tenant, subject), role_list in sorted(memberships.items())
    )
    return GrantSnapshot(revision=revision, memberships=rows, revoked_subject_ids=frozenset(revoked))
