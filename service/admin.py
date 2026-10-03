"""Minimal local administration stubs for grant snapshot lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from service.authorization import GrantSnapshot, Membership


@dataclass
class GrantAdminState:
    snapshot: GrantSnapshot

    def current_snapshot(self) -> GrantSnapshot:
        return self.snapshot

    def bump_revision(self, next_revision: str) -> GrantSnapshot:
        self.snapshot = GrantSnapshot(
            revision=next_revision,
            memberships=self.snapshot.memberships,
            revoked_subject_ids=self.snapshot.revoked_subject_ids,
        )
        return self.snapshot

    def revoke_subject(self, subject_id: str) -> GrantSnapshot:
        revoked = set(self.snapshot.revoked_subject_ids)
        revoked.add(subject_id)
        self.snapshot = GrantSnapshot(
            revision=self.snapshot.revision,
            memberships=self.snapshot.memberships,
            revoked_subject_ids=frozenset(revoked),
        )
        return self.snapshot

    def set_memberships(self, revision: str, memberships: tuple[Membership, ...]) -> GrantSnapshot:
        self.snapshot = GrantSnapshot(
            revision=revision,
            memberships=memberships,
            revoked_subject_ids=self.snapshot.revoked_subject_ids,
        )
        return self.snapshot
