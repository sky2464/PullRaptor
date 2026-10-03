"""Tenant-scoped job metadata and bounded atomic report storage (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Mapping

from service.contracts import (
    MAX_REPORT_BYTES,
    AuthorizedJob,
    JOB_STATES,
    Principal,
    ServiceContractError,
    ServiceRequest,
)

DEFAULT_MAX_QUEUED_PER_TENANT = 10
DEFAULT_MAX_ACTIVE_GLOBAL = 16
DEFAULT_MAX_CONCURRENT_WORKERS = 2


@dataclass(frozen=True)
class RetentionPolicy:
    report_days: int = 7
    metadata_days: int = 30


@dataclass(frozen=True)
class QuotaPolicy:
    max_queued_per_tenant: int = DEFAULT_MAX_QUEUED_PER_TENANT
    max_active_global: int = DEFAULT_MAX_ACTIVE_GLOBAL
    max_concurrent_workers: int = DEFAULT_MAX_CONCURRENT_WORKERS
    max_report_bytes: int = MAX_REPORT_BYTES


@dataclass(frozen=True)
class StoragePolicy:
    root: str
    tenant_namespaces: Mapping[str, str]
    retention: RetentionPolicy = RetentionPolicy()
    quotas: QuotaPolicy = QuotaPolicy()


class JobStorageError(ServiceContractError):
    """Job persistence or quota violation."""


@dataclass(frozen=True)
class JobReceipt:
    request_digest: str
    worker_digest: str
    report_digest: str
    coverage_state: str
    cause: str = ""

    def __post_init__(self) -> None:
        if self.coverage_state not in ("complete", "incomplete", "unknown"):
            raise ValueError(f"invalid coverage_state: {self.coverage_state!r}")


_TERMINAL_STATES = frozenset({"completed", "cancelled", "failed", "expired"})

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled", "failed", "expired"}),
    "running": frozenset({"completed", "cancelled", "failed", "expired"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "failed": frozenset(),
    "expired": frozenset(),
}


def idempotency_identity(
    request: ServiceRequest,
    principal: Principal,
    idempotency_key: str,
) -> str:
    """Bind caller key to tenant, subject, grants revision and full semantic request."""
    payload = {
        "tenant_id": principal.tenant_id,
        "subject_id": principal.subject_id,
        "grants_revision": principal.grants_revision,
        "idempotency_key": idempotency_key,
        "semantic_digest": request.semantic_digest(),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def report_digest(report_bytes: bytes) -> str:
    return hashlib.sha256(report_bytes).hexdigest()


class LocalJobStorage:
    """SQLite metadata plus per-tenant private report files under policy.root."""

    def __init__(self, policy: StoragePolicy) -> None:
        self._policy = policy
        root = Path(policy.root)
        root.mkdir(parents=True, exist_ok=True)
        self._db_path = root / "jobs.sqlite3"
        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        for tenant_id, namespace in policy.tenant_namespaces.items():
            (root / namespace).mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                repository_id TEXT NOT NULL,
                request_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                principal_subject TEXT NOT NULL,
                grants_revision TEXT NOT NULL,
                idempotency_identity TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL,
                cancelled_replay_blocked INTEGER NOT NULL DEFAULT 0,
                last_receipt_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                idempotency_key TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                idempotency_identity TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, tenant_id)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_tenant_state ON jobs(tenant_id, state)"
        )

    def _tenant_report_dir(self, tenant_id: str) -> Path:
        namespace = self._policy.tenant_namespaces.get(tenant_id)
        if namespace is None:
            raise JobStorageError("unknown_tenant", f"no storage namespace for tenant {tenant_id!r}")
        return Path(self._policy.root) / namespace / "reports"

    def enqueue(
        self,
        request: ServiceRequest,
        principal: Principal,
        idempotency_key: str,
        job_id: str,
    ) -> AuthorizedJob:
        if principal.tenant_id != request.tenant_id:
            raise JobStorageError("tenant_mismatch", "principal tenant does not match request")
        identity = idempotency_identity(request, principal, idempotency_key)
        existing = self._job_by_idempotency_identity(identity)
        if existing is not None:
            return existing
        collision = self._idempotency_key_collision(idempotency_key, tenant_id=principal.tenant_id, identity=identity)
        if collision:
            raise JobStorageError(
                "idempotency_collision",
                "idempotency key already bound to different semantic or authorization context",
            )
        cross_tenant = self._idempotency_key_other_tenant(idempotency_key, principal.tenant_id)
        if cross_tenant:
            raise JobStorageError(
                "tenant_key_collision",
                "idempotency key already used by another tenant",
            )
        self._enforce_queue_quota(principal.tenant_id)
        self._enforce_active_quota()
        import time

        now = time.time()
        digest = request.semantic_digest()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                """
                INSERT INTO jobs (
                    job_id, tenant_id, repository_id, request_digest, state,
                    principal_subject, grants_revision, idempotency_identity,
                    idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    request.tenant_id,
                    request.repository_id,
                    digest,
                    principal.subject_id,
                    principal.grants_revision,
                    identity,
                    idempotency_key,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO idempotency_keys (idempotency_key, tenant_id, idempotency_identity)
                VALUES (?, ?, ?)
                """,
                (idempotency_key, principal.tenant_id, identity),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return AuthorizedJob(
            job_id=job_id,
            tenant_id=request.tenant_id,
            repository_id=request.repository_id,
            request_digest=digest,
            state="queued",
        )

    def get_job(self, job_id: str) -> AuthorizedJob | None:
        row = self._conn.execute(
            "SELECT job_id, tenant_id, repository_id, request_digest, state FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return AuthorizedJob(
            job_id=row[0],
            tenant_id=row[1],
            repository_id=row[2],
            request_digest=row[3],
            state=row[4],
        )

    def transition(
        self,
        job_id: str,
        expected_state: str,
        next_state: str,
        receipt: JobReceipt | None = None,
    ) -> AuthorizedJob:
        if next_state not in JOB_STATES:
            raise JobStorageError("invalid_state", f"unknown state {next_state!r}")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                """
                SELECT job_id, tenant_id, repository_id, request_digest, state,
                       cancelled_replay_blocked
                FROM jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobStorageError("job_not_found", f"unknown job {job_id!r}")
            current_state = row[4]
            if current_state != expected_state:
                raise JobStorageError(
                    "state_conflict",
                    f"expected state {expected_state!r}, found {current_state!r}",
                )
            if next_state not in _ALLOWED_TRANSITIONS.get(current_state, frozenset()):
                raise JobStorageError(
                    "transition_denied",
                    f"cannot transition from {current_state!r} to {next_state!r}",
                )
            if next_state == "completed":
                raise JobStorageError(
                    "report_required",
                    "completed transition requires stored report via complete_with_report",
                )
            import time

            receipt_json = json.dumps(_receipt_to_dict(receipt), sort_keys=True) if receipt else None
            cancelled_block = 1 if next_state == "cancelled" else row[5]
            self._conn.execute(
                """
                UPDATE jobs SET state = ?, updated_at = ?, last_receipt_json = ?,
                    cancelled_replay_blocked = ?
                WHERE job_id = ?
                """,
                (next_state, time.time(), receipt_json, cancelled_block, job_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        job = self.get_job(job_id)
        assert job is not None
        return job

    def complete_with_report(
        self,
        job_id: str,
        report_bytes: bytes,
        receipt: JobReceipt,
    ) -> AuthorizedJob:
        if len(report_bytes) > self._policy.quotas.max_report_bytes:
            raise JobStorageError(
                "report_too_large",
                f"report exceeds {self._policy.quotas.max_report_bytes} bytes",
            )
        job = self.get_job(job_id)
        if job is None:
            raise JobStorageError("job_not_found", f"unknown job {job_id!r}")
        if job.state != "running":
            raise JobStorageError("state_conflict", f"job must be running, found {job.state!r}")
        report_dir = self._tenant_report_dir(job.tenant_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        final_path = report_dir / f"{job_id}.json"
        tmp_fd, tmp_name = tempfile.mkstemp(dir=report_dir, prefix=f".{job_id}-", suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "wb") as handle:
                handle.write(report_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, final_path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            self.transition(
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
            failed = self.get_job(job_id)
            assert failed is not None
            return failed
        digest = report_digest(report_bytes)
        if receipt.report_digest and receipt.report_digest != digest:
            raise JobStorageError("report_digest_mismatch", "report digest does not match bytes")
        completed_receipt = JobReceipt(
            request_digest=receipt.request_digest,
            worker_digest=receipt.worker_digest,
            report_digest=digest,
            coverage_state=receipt.coverage_state,
            cause=receipt.cause,
        )
        import time

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT state FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None or row[0] != "running":
                raise JobStorageError("state_conflict", "job no longer running")
            self._conn.execute(
                """
                UPDATE jobs SET state = 'completed', updated_at = ?, last_receipt_json = ?
                WHERE job_id = ?
                """,
                (time.time(), json.dumps(_receipt_to_dict(completed_receipt), sort_keys=True), job_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        done = self.get_job(job_id)
        assert done is not None
        return done

    def read_report_bytes(self, tenant_id: str, job_id: str) -> bytes:
        path = self._tenant_report_dir(tenant_id) / f"{job_id}.json"
        if not path.is_file():
            raise JobStorageError("report_not_found", f"no report for job {job_id!r}")
        data = path.read_bytes()
        if len(data) > self._policy.quotas.max_report_bytes:
            raise JobStorageError("report_too_large", "stored report exceeds quota")
        return data

    def last_receipt(self, job_id: str) -> JobReceipt | None:
        row = self._conn.execute(
            "SELECT last_receipt_json FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        obj = json.loads(row[0])
        return JobReceipt(
            request_digest=obj["request_digest"],
            worker_digest=obj["worker_digest"],
            report_digest=obj.get("report_digest", ""),
            coverage_state=obj["coverage_state"],
            cause=obj.get("cause", ""),
        )

    def is_cancelled_replay_blocked(self, request: ServiceRequest, principal: Principal, idempotency_key: str) -> bool:
        identity = idempotency_identity(request, principal, idempotency_key)
        row = self._conn.execute(
            "SELECT cancelled_replay_blocked, state FROM jobs WHERE idempotency_identity = ?",
            (identity,),
        ).fetchone()
        if row is None:
            return False
        return bool(row[0]) or row[1] == "cancelled"

    def recover_running_jobs(self) -> list[AuthorizedJob]:
        """After crash: running jobs become failed with honest partial receipt."""
        import time

        rows = self._conn.execute(
            "SELECT job_id FROM jobs WHERE state = 'running'"
        ).fetchall()
        recovered: list[AuthorizedJob] = []
        for (job_id,) in rows:
            receipt = JobReceipt(
                request_digest="",
                worker_digest="",
                report_digest="",
                coverage_state="unknown",
                cause="crash_recovery_partial",
            )
            self._conn.execute(
                """
                UPDATE jobs SET state = 'failed', updated_at = ?, last_receipt_json = ?
                WHERE job_id = ? AND state = 'running'
                """,
                (time.time(), json.dumps(_receipt_to_dict(receipt), sort_keys=True), job_id),
            )
            job = self.get_job(job_id)
            if job is not None:
                recovered.append(job)
        return recovered

    def count_queued(self, tenant_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE tenant_id = ? AND state = 'queued'",
            (tenant_id,),
        ).fetchone()
        return int(row[0])

    def count_active_global(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE state IN ('queued', 'running')",
        ).fetchone()
        return int(row[0])

    def _enforce_queue_quota(self, tenant_id: str) -> None:
        if self.count_queued(tenant_id) >= self._policy.quotas.max_queued_per_tenant:
            raise JobStorageError("queue_quota", "tenant queued job limit exceeded")

    def _enforce_active_quota(self) -> None:
        if self.count_active_global() >= self._policy.quotas.max_active_global:
            raise JobStorageError("active_quota", "global active job limit exceeded")

    def _job_by_idempotency_identity(self, identity: str) -> AuthorizedJob | None:
        row = self._conn.execute(
            """
            SELECT job_id, tenant_id, repository_id, request_digest, state
            FROM jobs WHERE idempotency_identity = ?
            """,
            (identity,),
        ).fetchone()
        if row is None:
            return None
        return AuthorizedJob(job_id=row[0], tenant_id=row[1], repository_id=row[2], request_digest=row[3], state=row[4])

    def _idempotency_key_collision(self, idempotency_key: str, tenant_id: str, identity: str) -> bool:
        row = self._conn.execute(
            """
            SELECT idempotency_identity FROM idempotency_keys
            WHERE idempotency_key = ? AND tenant_id = ?
            """,
            (idempotency_key, tenant_id),
        ).fetchone()
        if row is None:
            return False
        return row[0] != identity

    def _idempotency_key_other_tenant(self, idempotency_key: str, tenant_id: str) -> bool:
        row = self._conn.execute(
            """
            SELECT tenant_id FROM idempotency_keys
            WHERE idempotency_key = ? AND tenant_id != ?
            LIMIT 1
            """,
            (idempotency_key, tenant_id),
        ).fetchone()
        return row is not None


def _receipt_to_dict(receipt: JobReceipt | None) -> dict[str, Any]:
    if receipt is None:
        return {}
    return {
        "request_digest": receipt.request_digest,
        "worker_digest": receipt.worker_digest,
        "report_digest": receipt.report_digest,
        "coverage_state": receipt.coverage_state,
        "cause": receipt.cause,
    }


def storage_policy_for_tests(root: str, tenants: Mapping[str, str]) -> StoragePolicy:
    return StoragePolicy(root=root, tenant_namespaces=dict(tenants))
