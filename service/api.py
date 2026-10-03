"""In-process /v1 review service handlers with injected mock authority and storage."""

from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Any

from service.contracts import (
    API_VERSION,
    AuthorizedJob,
    AuthorizationResult,
    Authority,
    CapabilityDocument,
    ConnectorRegistry,
    Principal,
    ReportAccess,
    ResourceIdentity,
    ServiceAction,
    ServiceContractError,
    ServiceRequest,
    authorized_job_to_dict,
    decode_report_bytes,
)


@dataclass
class AuthorizationAudit:
    last_result: AuthorizationResult | None = None


class ReviewService:
    """Local bounded API; no network transport and no kernel imports."""

    def __init__(
        self,
        *,
        authority: Authority,
        registry: ConnectorRegistry,
        reports: ReportAccess,
        capabilities: CapabilityDocument | None = None,
    ) -> None:
        self._authority = authority
        self._registry = registry
        self._reports = reports
        self._capabilities = capabilities or CapabilityDocument(schema="1", admitted_rows=())
        self._jobs: dict[str, AuthorizedJob] = {}
        self._audit = AuthorizationAudit()

    @property
    def authorization(self) -> AuthorizationResult | None:
        return self._audit.last_result

    def submit(self, request: ServiceRequest, principal: Principal) -> AuthorizedJob:
        resource = ResourceIdentity(
            tenant_id=request.tenant_id,
            repository_id=request.repository_id,
        )
        decision = self._authorize(principal, ServiceAction("submit"), resource)
        if decision.status == "denied":
            raise ServiceContractError("authorization_denied", decision.cause or "submit denied")
        if principal.tenant_id != request.tenant_id:
            raise ServiceContractError("tenant_mismatch", "principal tenant does not match request")
        resolution = self._registry.resolve_repository(principal, request.repository_id)
        if not resolution.authorized:
            raise ServiceContractError(
                "repository_denied",
                resolution.cause or "repository not authorized",
            )
        job_id = secrets.token_hex(16)
        job = AuthorizedJob(
            job_id=job_id,
            tenant_id=request.tenant_id,
            repository_id=resolution.repository_id,
            request_digest=request.semantic_digest(),
            state="queued",
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str, principal: Principal) -> AuthorizedJob:
        job = self._require_job(job_id)
        decision = self._authorize(
            principal,
            ServiceAction("get_job"),
            ResourceIdentity(tenant_id=job.tenant_id, repository_id=job.repository_id, job_id=job_id),
        )
        if decision.status == "denied":
            raise ServiceContractError("authorization_denied", decision.cause or "get_job denied")
        if principal.tenant_id != job.tenant_id:
            raise ServiceContractError("tenant_mismatch", "principal tenant does not match job")
        return job

    def get_report(self, job_id: str, principal: Principal) -> dict[str, Any]:
        job = self._require_job(job_id)
        decision = self._authorize(
            principal,
            ServiceAction("get_report"),
            ResourceIdentity(tenant_id=job.tenant_id, repository_id=job.repository_id, job_id=job_id),
        )
        self._audit.last_result = decision
        if decision.status == "denied":
            raise ServiceContractError("authorization_denied", decision.cause or "get_report denied")
        if principal.tenant_id != job.tenant_id:
            raise ServiceContractError("tenant_mismatch", "principal tenant does not match job")
        raw = self._reports.read_report_bytes(job.tenant_id, job_id)
        return decode_report_bytes(raw)

    def cancel(self, job_id: str, principal: Principal) -> AuthorizedJob:
        job = self._require_job(job_id)
        decision = self._authorize(
            principal,
            ServiceAction("cancel"),
            ResourceIdentity(tenant_id=job.tenant_id, repository_id=job.repository_id, job_id=job_id),
        )
        if decision.status == "denied":
            raise ServiceContractError("authorization_denied", decision.cause or "cancel denied")
        if principal.tenant_id != job.tenant_id:
            raise ServiceContractError("tenant_mismatch", "principal tenant does not match job")
        if job.state in ("completed", "cancelled", "failed", "expired"):
            return job
        updated = AuthorizedJob(
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            repository_id=job.repository_id,
            request_digest=job.request_digest,
            state="cancelled",
        )
        self._jobs[job_id] = updated
        return updated

    def capabilities(self, principal: Principal) -> CapabilityDocument:
        decision = self._authorize(
            principal,
            ServiceAction("capabilities"),
            ResourceIdentity(tenant_id=principal.tenant_id),
        )
        if decision.status == "denied":
            raise ServiceContractError(
                "authorization_denied",
                decision.cause or "capabilities denied",
            )
        return self._capabilities

    def seed_job(self, job: AuthorizedJob) -> None:
        """Test helper: register a job without going through submit."""
        self._jobs[job.job_id] = job

    def api_version(self) -> str:
        return API_VERSION

    def _authorize(
        self,
        principal: Principal,
        action: ServiceAction,
        resource: ResourceIdentity,
    ) -> AuthorizationResult:
        decision = self._authority.authorize(principal, action, resource)
        self._audit.last_result = decision
        return decision

    def _require_job(self, job_id: str) -> AuthorizedJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ServiceContractError("job_not_found", f"unknown job {job_id!r}")
        return job


def job_response(job: AuthorizedJob) -> dict[str, Any]:
    return {"api_version": API_VERSION, "job": authorized_job_to_dict(job)}
