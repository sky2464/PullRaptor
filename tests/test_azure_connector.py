"""E09-T1 Azure acquisition connector tests (fake transport only)."""

from __future__ import annotations

import time
import unittest

from pullraptor.azure_connector import (
    AzureConnectorPolicy,
    AzureEventHint,
    AzureReviewContext,
    ConnectorCredentials,
    FakeAzureTransport,
    TransportPolicy,
    resolve_azure_review,
)

_HEAD_A = "a" * 40
_HEAD_B = "b" * 40
_HEAD_C = "c" * 40
_REPO = "repo-guid-1"
_ORG = "contoso"
_PROJECT = "proj-1"


def _policy(**overrides: object) -> AzureConnectorPolicy:
    base = {
        "organization_id": _ORG,
        "allowed_repository_ids": frozenset({_REPO}),
        "api_version": "7.1",
        "transport_policy": TransportPolicy(),
    }
    base.update(overrides)
    return AzureConnectorPolicy(**base)


def _credentials(**overrides: object) -> ConnectorCredentials:
    base = {
        "credential_id": "cred-1",
        "organization_id": _ORG,
        "scopes": frozenset({"vso.code"}),
        "expires_at": time.time() + 3600.0,
    }
    base.update(overrides)
    return ConnectorCredentials(**base)


def _iteration_fixture(
    iteration_id: int,
    *,
    source: str = _HEAD_A,
    policy_digest: str = "policy-1",
) -> tuple[int, dict]:
    return (
        200,
        {
            "iteration_id": iteration_id,
            "source_head": source,
            "target_tip": _HEAD_B,
            "comparison_base": _HEAD_C,
            "policy_digest": policy_digest,
            "scope_digest": "scope-1",
            "reviewer_digest": "reviewer-1",
        },
    )


class TestAzureConnector(unittest.TestCase):
    def test_wrong_org_repository_denied(self) -> None:
        transport = FakeAzureTransport(fixtures={}, sent=[])
        acquisition = resolve_azure_review(
            42,
            connector=_policy(allowed_repository_ids=frozenset({"other-repo"})),
            credentials=_credentials(),
            transport=transport,
            project_id=_PROJECT,
            repository_id=_REPO,
            iteration_id=3,
        )
        self.assertEqual(acquisition.status, "denied")
        self.assertEqual(acquisition.acquired_source_bytes, 0)
        self.assertEqual(len(transport.sent), 0)

    def test_iteration_exact_binding(self) -> None:
        key = ("get_pull_request_iteration", _ORG, _REPO, 7, 2)
        transport = FakeAzureTransport(fixtures={key: _iteration_fixture(2)}, sent=[])
        acquisition = resolve_azure_review(
            7,
            connector=_policy(),
            credentials=_credentials(),
            transport=transport,
            project_id=_PROJECT,
            repository_id=_REPO,
            iteration_id=2,
        )
        self.assertEqual(acquisition.status, "ok")
        self.assertIsNotNone(acquisition.context)
        assert acquisition.context is not None
        self.assertEqual(acquisition.context.iteration_id, 2)
        self.assertEqual(acquisition.context.source_head, _HEAD_A)
        self.assertGreater(acquisition.acquired_source_bytes, 0)

    def test_same_head_target_policy_drift(self) -> None:
        key = ("get_pull_request_iteration", _ORG, _REPO, 5, 4)
        transport = FakeAzureTransport(
            fixtures={key: _iteration_fixture(4, policy_digest="policy-new")},
            sent=[],
        )
        prior = AzureReviewContext(
            platform="azure_devops_services",
            organization_id=_ORG,
            project_id=_PROJECT,
            repository_id=_REPO,
            pr_id=5,
            iteration_id=4,
            source_head=_HEAD_A,
            target_tip=_HEAD_B,
            comparison_base=_HEAD_C,
            policy_digest="policy-old",
            scope_digest="scope-1",
            reviewer_digest="reviewer-1",
        )
        acquisition = resolve_azure_review(
            5,
            connector=_policy(),
            credentials=_credentials(),
            transport=transport,
            project_id=_PROJECT,
            repository_id=_REPO,
            iteration_id=4,
            prior_context=prior,
        )
        self.assertEqual(acquisition.status, "stale")
        self.assertEqual(acquisition.cause, "target_policy_drift")

    def test_expired_credentials_unavailable(self) -> None:
        transport = FakeAzureTransport(fixtures={}, sent=[])
        acquisition = resolve_azure_review(
            1,
            connector=_policy(),
            credentials=_credentials(expires_at=time.time() - 10.0),
            transport=transport,
            project_id=_PROJECT,
            repository_id=_REPO,
            iteration_id=1,
        )
        self.assertEqual(acquisition.status, "unavailable")
        self.assertEqual(acquisition.cause, "credentials_expired")
        self.assertEqual(acquisition.acquired_source_bytes, 0)

    def test_event_refs_not_authoritative(self) -> None:
        key = ("get_pull_request_iteration", _ORG, _REPO, 9, 1)
        transport = FakeAzureTransport(fixtures={key: _iteration_fixture(1)}, sent=[])
        hint = AzureEventHint(
            repository_id="event-only-repo",
            source_head="f" * 40,
            iteration_id=99,
        )
        acquisition = resolve_azure_review(
            9,
            connector=_policy(),
            credentials=_credentials(),
            transport=transport,
            project_id=_PROJECT,
            repository_id=_REPO,
            iteration_id=1,
            event_hint=hint,
        )
        self.assertEqual(acquisition.status, "denied")
        self.assertEqual(acquisition.cause, "event_repository_not_authoritative")
        self.assertEqual(acquisition.acquired_source_bytes, 0)


if __name__ == "__main__":
    unittest.main()
