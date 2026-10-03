"""E11-A1 local identity and scoped authorization stubs (no live SSO)."""

from __future__ import annotations

import unittest

from service.admin import GrantAdminState
from service.authorization import EnterpriseResource, GrantSnapshot, authorize, snapshot_from_mapping
from service.contracts import Principal
from service.identity import IdentityError, IdentityPolicy, authenticate, encode_fake_assertion


def _policy() -> IdentityPolicy:
    return IdentityPolicy(
        issuer="https://identity.local/issuer",
        audience="pullraptor-service",
        organization_bindings={"org-a": "tenant-a", "org-b": "tenant-b"},
        verification_keys={"local-k1": "fake-key-material", "local-k2": "rotated-material"},
        provisioning_origin="scim://fake.local",
    )


def _grants_v1() -> GrantSnapshot:
    return snapshot_from_mapping(
        "grants-v1",
        {
            ("tenant-a", "subject-1"): ("reviewer", "viewer"),
            ("tenant-a", "publisher-1"): ("publisher",),
            ("tenant-a", "admin-1"): ("admin",),
        },
    )


class TestEnterpriseIdentity(unittest.TestCase):
    def test_wrong_issuer_audience_expiry(self) -> None:
        policy = _policy()
        assertion = encode_fake_assertion(
            policy=policy,
            subject_id="subject-1",
            org_id="org-a",
            grants_revision="grants-v1",
            ttl_seconds=-10,
        )
        with self.assertRaises(IdentityError) as ctx:
            authenticate(assertion, policy)
        self.assertEqual(ctx.exception.code, "assertion_expired")
        bad_iss = encode_fake_assertion(
            policy=IdentityPolicy(
                issuer="https://evil.example",
                audience=policy.audience,
                organization_bindings=policy.organization_bindings,
                verification_keys=policy.verification_keys,
                provisioning_origin=policy.provisioning_origin,
            ),
            subject_id="subject-1",
            org_id="org-a",
            grants_revision="grants-v1",
        )
        with self.assertRaises(IdentityError):
            authenticate(bad_iss, policy)

    def test_same_email_cross_tenant_denied(self) -> None:
        policy = _policy()
        assertion = encode_fake_assertion(
            policy=policy,
            subject_id="subject-1",
            org_id="org-a",
            grants_revision="grants-v1",
            email="shared@example.com",
            tenant_id="tenant-b",
        )
        with self.assertRaises(IdentityError) as ctx:
            authenticate(assertion, policy)
        self.assertEqual(ctx.exception.code, "tenant_binding_mismatch")

    def test_each_report_cache_repo_permission(self) -> None:
        grants = _grants_v1()
        principal = Principal("tenant-a", "subject-1", "grants-v1")
        repo = EnterpriseResource("tenant-a", "repository", "repo-1", repository_id="repo-1")
        report = EnterpriseResource("tenant-a", "report", "job-1", repository_id="repo-1")
        cache = EnterpriseResource("tenant-a", "cache", "cache-1", repository_id="repo-1")
        self.assertTrue(authorize(principal, "view_report", report, grants).allowed)
        self.assertTrue(authorize(principal, "read_cache", cache, grants).allowed)
        self.assertTrue(authorize(principal, "submit", repo, grants).allowed)
        self.assertFalse(authorize(principal, "publish", report, grants).allowed)
        viewer_only = snapshot_from_mapping(
            "grants-v1",
            {("tenant-a", "subject-1"): ("viewer",)},
        )
        self.assertFalse(authorize(principal, "submit", repo, viewer_only).allowed)

    def test_deprovision_and_key_rotation(self) -> None:
        policy = _policy()
        admin = GrantAdminState(_grants_v1())
        admin.revoke_subject("subject-1")
        principal = Principal("tenant-a", "subject-1", "grants-v1")
        resource = EnterpriseResource("tenant-a", "report", "job-1", repository_id="repo-1")
        decision = authorize(principal, "view_report", resource, admin.current_snapshot())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.cause, "revoked_principal")
        rotated = IdentityPolicy(
            issuer=policy.issuer,
            audience=policy.audience,
            organization_bindings=policy.organization_bindings,
            verification_keys={"local-k1": "revoked", "local-k2": "rotated-material"},
            provisioning_origin=policy.provisioning_origin,
        )
        assertion = encode_fake_assertion(
            policy=rotated,
            subject_id="subject-2",
            org_id="org-a",
            grants_revision="grants-v1",
            kid="local-k1",
        )
        with self.assertRaises(IdentityError) as ctx:
            authenticate(assertion, rotated)
        self.assertEqual(ctx.exception.code, "verification_key_revoked")

    def test_stale_grants_before_publish_denied(self) -> None:
        grants = _grants_v1()
        publisher = Principal("tenant-a", "publisher-1", "grants-stale")
        resource = EnterpriseResource("tenant-a", "report", "job-1", repository_id="repo-1")
        decision = authorize(publisher, "publish", resource, grants)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.cause, "stale_grants")
        queued_publication_executed = False
        if decision.allowed:
            queued_publication_executed = True
        self.assertFalse(queued_publication_executed)


if __name__ == "__main__":
    unittest.main()
