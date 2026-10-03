"""Local /v1 service API contract tests (mock authority and storage only)."""

from __future__ import annotations

import json
import unittest

from sdk.pullraptor_client import PullRaptorClient, encode_request, request_from_dict
from service.api import ReviewService
from service.contracts import (
    AuthorizedJob,
    CapabilityDocument,
    CountingReportAccess,
    DenyByDefaultAuthority,
    Grant,
    InMemoryConnectorRegistry,
    InMemoryReportAccess,
    Principal,
    ServiceContractError,
    ServiceRequest,
    decode_submit_envelope,
    service_request_to_dict,
)


def _sample_request(**overrides: str) -> ServiceRequest:
    base = {
        "tenant_id": "tenant-a",
        "repository_id": "repo-registered",
        "base_tip": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "comparison_base": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "head_or_snapshot": "cccccccccccccccccccccccccccccccccccccccc",
        "policy_origin": "coordinator:trusted-base",
        "scope_digest": "scope-digest-1",
        "profile": "structural",
        "reviewer_digest": "reviewer-digest-1",
    }
    base.update(overrides)
    return request_from_dict(base)


def _principal(**overrides: str) -> Principal:
    base = {
        "tenant_id": "tenant-a",
        "subject_id": "subject-1",
        "grants_revision": "grants-v1",
    }
    base.update(overrides)
    return Principal(**base)


def _grants_for_tenant(tenant: str = "tenant-a") -> tuple[Grant, ...]:
    repo = "repo-registered"
    rev = "grants-v1"
    subject = "subject-1"
    return (
        Grant(tenant, subject, rev, "submit", tenant, repository_id=repo),
        Grant(tenant, subject, rev, "get_job", tenant, repository_id=repo),
        Grant(tenant, subject, rev, "get_report", tenant, repository_id=repo),
        Grant(tenant, subject, rev, "cancel", tenant, repository_id=repo),
        Grant(tenant, subject, rev, "capabilities", tenant),
    )


def _limit_failure_report() -> bytes:
    payload = {
        "schema": "1",
        "kind": "limit_failure",
        "known_inputs": {"head": "cccccccccccccccccccccccccccccccccccccccc"},
        "exit_code": 2,
        "analysis_complete": False,
        "details_omitted": True,
        "cause": "deadline_exceeded",
        "limit": {"review_timeout_seconds": 60},
        "omitted_domains": [],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class TestServiceAPIContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.job_id = "job-limit-failure"
        self.reports = InMemoryReportAccess(
            {("tenant-a", self.job_id): _limit_failure_report()},
        )
        self.counting_reports = CountingReportAccess(self.reports)
        self.registry = InMemoryConnectorRegistry({"repo-registered": "repo-registered"})
        self.capabilities = CapabilityDocument(
            schema="1",
            admitted_rows=(("structural", "python", "review"),),
        )
        self.service = ReviewService(
            authority=DenyByDefaultAuthority(_grants_for_tenant()),
            registry=self.registry,
            reports=self.counting_reports,
            capabilities=self.capabilities,
        )
        self.service.seed_job(
            AuthorizedJob(
                job_id=self.job_id,
                tenant_id="tenant-a",
                repository_id="repo-registered",
                request_digest="digest-1",
                state="completed",
            ),
        )
        self.client = PullRaptorClient(self.service, _principal())

    def test_arbitrary_url_path_denied(self) -> None:
        for bad_repo in (
            "https://evil.example/org/repo",
            "/var/tmp/repo",
            "file:///etc/passwd",
        ):
            with self.assertRaises(ServiceContractError):
                _sample_request(repository_id=bad_repo)
        denied_client = PullRaptorClient(
            ReviewService(
                authority=DenyByDefaultAuthority(_grants_for_tenant()),
                registry=self.registry,
                reports=self.counting_reports,
            ),
            _principal(),
        )
        with self.assertRaises(ServiceContractError):
            denied_client.submit(_sample_request(repository_id="repo-unknown"))

    def test_wrong_tenant_each_endpoint(self) -> None:
        wrong = PullRaptorClient(self.service, _principal(tenant_id="tenant-b"))
        with self.assertRaises(ServiceContractError):
            wrong.get_job(self.job_id)
        with self.assertRaises(ServiceContractError):
            wrong.get_report(self.job_id)
        with self.assertRaises(ServiceContractError):
            wrong.cancel(self.job_id)
        with self.assertRaises(ServiceContractError):
            wrong.capabilities()
        with self.assertRaises(ServiceContractError):
            wrong.submit(_sample_request(tenant_id="tenant-b"))

    def test_unknown_fields_and_version(self) -> None:
        envelope = {
            "api_version": 1,
            "request": service_request_to_dict(_sample_request()),
            "unexpected": True,
        }
        raw = json.dumps(envelope).encode("utf-8")
        with self.assertRaises(ServiceContractError):
            decode_submit_envelope(raw)
        bad_version = json.dumps(
            {"api_version": 99, "request": service_request_to_dict(_sample_request())},
        ).encode("utf-8")
        with self.assertRaises(ServiceContractError):
            decode_submit_envelope(bad_version)
        request = service_request_to_dict(_sample_request())
        request["extra_field"] = "nope"
        with self.assertRaises(ServiceContractError):
            request_from_dict(request)

    def test_limit_failure_preserved(self) -> None:
        report = self.client.get_report(self.job_id)
        self.assertEqual(report["kind"], "limit_failure")
        self.assertFalse(report["analysis_complete"])
        roundtrip = self.client.roundtrip_report(self.job_id)
        self.assertEqual(roundtrip["kind"], "limit_failure")
        self.assertFalse(roundtrip["analysis_complete"])

    def test_sdk_coverage_roundtrip(self) -> None:
        denied_service = ReviewService(
            authority=DenyByDefaultAuthority(),
            registry=self.registry,
            reports=self.counting_reports,
        )
        denied_service.seed_job(
            AuthorizedJob(
                job_id=self.job_id,
                tenant_id="tenant-a",
                repository_id="repo-registered",
                request_digest="digest-1",
                state="completed",
            ),
        )
        unauthorized = PullRaptorClient(denied_service, _principal())
        self.counting_reports.reset_read_count()
        with self.assertRaises(ServiceContractError):
            unauthorized.get_report(self.job_id)
        authorization = denied_service.authorization
        self.assertIsNotNone(authorization)
        assert authorization is not None
        self.assertEqual(authorization.status, "denied")
        self.assertEqual(self.counting_reports.bytes_read, 0)

        caps = self.client.capabilities()
        self.assertEqual(caps["capabilities"]["schema"], "1")
        self.assertEqual(len(caps["capabilities"]["admitted_rows"]), 1)

        submitted = self.client.submit(_sample_request())
        job_id = submitted["job"]["job_id"]
        job = self.client.get_job(job_id)
        self.assertEqual(job["job"]["state"], "queued")

        patch_request = request_from_dict(
            {
                **service_request_to_dict(_sample_request()),
                "request_kind": "patch_only",
                "scope_digest": "reduced-scope",
            },
        )
        patch_bytes = encode_request(patch_request)
        patch_job = self.client.submit_bytes(patch_bytes)
        self.assertEqual(patch_job["job"]["state"], "queued")

        roundtrip = self.client.roundtrip_report(self.job_id)
        self.assertFalse(roundtrip["analysis_complete"])


if __name__ == "__main__":
    unittest.main()
