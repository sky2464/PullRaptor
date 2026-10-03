"""Recoverable bounded job queue over local storage contracts."""

from __future__ import annotations

import secrets
from typing import Protocol

from service.contracts import AuthorizedJob, Principal, ServiceRequest
from service.storage import (
    JobReceipt,
    JobStorageError,
    LocalJobStorage,
    StoragePolicy,
    idempotency_identity,
)


class ReportWriteHook(Protocol):
    """Test hook to simulate report storage failures without touching disk."""

    def before_write(self, tenant_id: str, job_id: str, report_bytes: bytes) -> None: ...


class JobStore:
    """Enqueue and transition jobs with idempotency and quota enforcement."""

    def __init__(
        self,
        storage: LocalJobStorage,
        *,
        report_write_hook: ReportWriteHook | None = None,
    ) -> None:
        self._storage = storage
        self._report_write_hook = report_write_hook

    @property
    def storage(self) -> LocalJobStorage:
        return self._storage

    def enqueue(
        self,
        request: ServiceRequest,
        principal: Principal,
        idempotency_key: str,
    ) -> AuthorizedJob:
        if self._storage.is_cancelled_replay_blocked(request, principal, idempotency_key):
            raise JobStorageError(
                "cancelled_replay_denied",
                "cancelled idempotent request cannot be silently resubmitted",
            )
        job_id = secrets.token_hex(16)
        return self._storage.enqueue(request, principal, idempotency_key, job_id)

    def transition(
        self,
        job_id: str,
        expected_state: str,
        next_state: str,
        receipt: JobReceipt | None = None,
    ) -> AuthorizedJob:
        return self._storage.transition(job_id, expected_state, next_state, receipt)

    def complete_with_report(
        self,
        job_id: str,
        report_bytes: bytes,
        receipt: JobReceipt,
    ) -> AuthorizedJob:
        job = self._storage.get_job(job_id)
        if job is None:
            raise JobStorageError("job_not_found", f"unknown job {job_id!r}")
        if self._report_write_hook is not None:
            try:
                self._report_write_hook.before_write(job.tenant_id, job_id, report_bytes)
            except OSError:
                return self._storage.transition(
                    job_id,
                    "running",
                    "failed",
                    JobReceipt(
                        request_digest=receipt.request_digest,
                        worker_digest=receipt.worker_digest,
                        report_digest="",
                        coverage_state=receipt.coverage_state,
                        cause="report_storage_failed",
                    ),
                )
        return self._storage.complete_with_report(job_id, report_bytes, receipt)

    def recover_after_crash(self) -> list[AuthorizedJob]:
        return self._storage.recover_running_jobs()

    def idempotency_identity(
        self,
        request: ServiceRequest,
        principal: Principal,
        idempotency_key: str,
    ) -> str:
        return idempotency_identity(request, principal, idempotency_key)


def open_job_store(policy: StoragePolicy) -> JobStore:
    return JobStore(LocalJobStorage(policy))
