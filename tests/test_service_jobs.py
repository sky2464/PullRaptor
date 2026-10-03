"""E10-A2 local job persistence, idempotency and storage tests."""

from __future__ import annotations

import json
import tempfile
import unittest

from service.contracts import Principal, ServiceRequest
from service.jobs import JobStore, open_job_store
from service.storage import (
    JobReceipt,
    JobStorageError,
    QuotaPolicy,
    StoragePolicy,
    storage_policy_for_tests,
)


def _request(**overrides: str) -> ServiceRequest:
    base = {
        "tenant_id": "tenant-a",
        "repository_id": "repo-1",
        "base_tip": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "comparison_base": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "head_or_snapshot": "cccccccccccccccccccccccccccccccccccccccc",
        "policy_origin": "coordinator:trusted-base",
        "scope_digest": "scope-1",
        "profile": "structural",
        "reviewer_digest": "reviewer-1",
    }
    base.update(overrides)
    return ServiceRequest(**base)


def _principal(**overrides: str) -> Principal:
    base = {
        "tenant_id": "tenant-a",
        "subject_id": "subject-1",
        "grants_revision": "grants-v1",
    }
    base.update(overrides)
    return Principal(**base)


def _limit_failure_report() -> bytes:
    payload = {
        "schema": "1",
        "kind": "limit_failure",
        "known_inputs": {},
        "exit_code": 2,
        "analysis_complete": False,
        "details_omitted": True,
        "cause": "deadline_exceeded",
        "limit": {"review_timeout_seconds": 60},
        "omitted_domains": [],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class FailingReportWrite:
    """Simulates atomic report write failure without relying on filesystem permissions."""

    def before_write(self, tenant_id: str, job_id: str, report_bytes: bytes) -> None:
        raise OSError("simulated report storage failure")


class TestServiceJobs(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._policy = storage_policy_for_tests(
            self._tmpdir.name,
            {"tenant-a": "ns-a", "tenant-b": "ns-b"},
        )
        self._store = open_job_store(self._policy)

    def tearDown(self) -> None:
        self._store.storage.close()
        self._tmpdir.cleanup()

    def test_idempotency_all_semantic_inputs(self) -> None:
        req = _request()
        principal = _principal()
        key = "idem-1"
        first = self._store.enqueue(req, principal, key)
        second = self._store.enqueue(req, principal, key)
        self.assertEqual(first.job_id, second.job_id)
        changed = _request(scope_digest="scope-2")
        with self.assertRaises(JobStorageError) as ctx:
            self._store.enqueue(changed, principal, key)
        self.assertEqual(ctx.exception.code, "idempotency_collision")

    def test_tenant_key_collision_denied(self) -> None:
        req_a = _request(tenant_id="tenant-a")
        req_b = _request(tenant_id="tenant-b")
        key = "shared-key"
        self._store.enqueue(req_a, _principal(tenant_id="tenant-a"), key)
        policy_b = storage_policy_for_tests(
            self._tmpdir.name,
            {"tenant-a": "ns-a", "tenant-b": "ns-b"},
        )
        store_b = open_job_store(policy_b)
        try:
            with self.assertRaises(JobStorageError) as ctx:
                store_b.enqueue(req_b, _principal(tenant_id="tenant-b"), key)
            self.assertEqual(ctx.exception.code, "tenant_key_collision")
        finally:
            store_b.storage.close()

    def test_cancel_worker_race(self) -> None:
        job = self._store.enqueue(_request(), _principal(), "race-1")
        running = self._store.transition(job.job_id, "queued", "running")
        self.assertEqual(running.state, "running")
        cancelled = self._store.transition(job.job_id, "running", "cancelled")
        self.assertEqual(cancelled.state, "cancelled")
        with self.assertRaises(JobStorageError) as ctx:
            self._store.enqueue(_request(), _principal(), "race-1")
        self.assertEqual(ctx.exception.code, "cancelled_replay_denied")

    def test_crash_recovery_partial(self) -> None:
        job = self._store.enqueue(_request(), _principal(), "crash-1")
        self._store.transition(job.job_id, "queued", "running")
        recovered = self._store.recover_after_crash()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].state, "failed")
        receipt = self._store.storage.last_receipt(job.job_id)
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt.cause, "crash_recovery_partial")
        self.assertEqual(receipt.coverage_state, "unknown")

    def test_report_write_failure_not_completed(self) -> None:
        hook = FailingReportWrite()
        store = JobStore(self._store.storage, report_write_hook=hook)
        job = store.enqueue(_request(), _principal(), "write-fail")
        store.transition(job.job_id, "queued", "running")
        report = _limit_failure_report()
        receipt = JobReceipt(
            request_digest=job.request_digest,
            worker_digest="worker-1",
            report_digest="",
            coverage_state="incomplete",
        )
        failed = store.complete_with_report(job.job_id, report, receipt)
        self.assertEqual(failed.state, "failed")
        stored_receipt = store.storage.last_receipt(job.job_id)
        self.assertIsNotNone(stored_receipt)
        assert stored_receipt is not None
        self.assertEqual(stored_receipt.cause, "report_storage_failed")
        analysis = json.loads(report.decode("utf-8"))
        self.assertFalse(analysis["analysis_complete"])

    def test_queue_storage_quota(self) -> None:
        tight = StoragePolicy(
            root=self._policy.root,
            tenant_namespaces=self._policy.tenant_namespaces,
            quotas=QuotaPolicy(max_queued_per_tenant=2, max_active_global=16),
        )
        store = open_job_store(tight)
        try:
            store.enqueue(_request(), _principal(), "q1")
            store.enqueue(_request(head_or_snapshot="d" * 40), _principal(), "q2")
            with self.assertRaises(JobStorageError) as ctx:
                store.enqueue(_request(head_or_snapshot="e" * 40), _principal(), "q3")
            self.assertEqual(ctx.exception.code, "queue_quota")
        finally:
            store.storage.close()


if __name__ == "__main__":
    unittest.main()
