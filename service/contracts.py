"""Versioned local service API records and deny-by-default authorization contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence

API_VERSION = "v1"
API_ENVELOPE_VERSION = 1
MAX_ENVELOPE_BYTES = 1_048_576
MAX_REPORT_BYTES = 8_388_608

JOB_STATES = frozenset({"queued", "running", "completed", "cancelled", "failed", "expired"})


class ServiceContractError(ValueError):
    """Bounded contract violation for service API payloads."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    subject_id: str
    grants_revision: str


@dataclass(frozen=True)
class ServiceRequest:
    tenant_id: str
    repository_id: str
    base_tip: str
    comparison_base: str
    head_or_snapshot: str
    policy_origin: str
    scope_digest: str
    profile: str
    reviewer_digest: str
    request_kind: str = "full"

    def semantic_digest(self) -> str:
        payload = {
            "tenant_id": self.tenant_id,
            "repository_id": self.repository_id,
            "base_tip": self.base_tip,
            "comparison_base": self.comparison_base,
            "head_or_snapshot": self.head_or_snapshot,
            "policy_origin": self.policy_origin,
            "scope_digest": self.scope_digest,
            "profile": self.profile,
            "reviewer_digest": self.reviewer_digest,
            "request_kind": self.request_kind,
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorizedJob:
    job_id: str
    tenant_id: str
    repository_id: str
    request_digest: str
    state: str

    def __post_init__(self) -> None:
        if self.state not in JOB_STATES:
            raise ValueError(f"invalid job state: {self.state!r}")


@dataclass(frozen=True)
class CapabilityDocument:
    schema: str
    admitted_rows: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "admitted_rows": [list(row) for row in self.admitted_rows],
        }


@dataclass(frozen=True)
class CompletionEvent:
    event_id: str
    tenant_id: str
    job_id: str
    report_digest: str
    state: str
    issued_at: str


@dataclass(frozen=True)
class AuthorizationResult:
    status: str
    cause: str = ""

    def __post_init__(self) -> None:
        if self.status not in ("allowed", "denied"):
            raise ValueError(f"invalid authorization status: {self.status!r}")


@dataclass(frozen=True)
class ServiceAction:
    name: str

    def __post_init__(self) -> None:
        if self.name not in (
            "submit",
            "get_job",
            "get_report",
            "cancel",
            "capabilities",
        ):
            raise ValueError(f"unknown service action: {self.name!r}")


@dataclass(frozen=True)
class ResourceIdentity:
    tenant_id: str
    repository_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class Grant:
    tenant_id: str
    subject_id: str
    grants_revision: str
    action: str
    resource_tenant_id: str
    repository_id: str | None = None
    job_id: str | None = None


class Authority(Protocol):
    def authorize(
        self,
        principal: Principal,
        action: ServiceAction,
        resource: ResourceIdentity,
    ) -> AuthorizationResult: ...


class DenyByDefaultAuthority:
    """Local test authority: explicit grants only; default deny."""

    def __init__(self, grants: Sequence[Grant] = ()) -> None:
        self._grants = tuple(grants)

    def authorize(
        self,
        principal: Principal,
        action: ServiceAction,
        resource: ResourceIdentity,
    ) -> AuthorizationResult:
        for grant in self._grants:
            if grant.grants_revision != principal.grants_revision:
                continue
            if grant.tenant_id != principal.tenant_id:
                continue
            if grant.subject_id != principal.subject_id:
                continue
            if grant.action != action.name:
                continue
            if grant.resource_tenant_id != resource.tenant_id:
                continue
            if grant.repository_id is not None and grant.repository_id != resource.repository_id:
                continue
            if grant.job_id is not None and grant.job_id != resource.job_id:
                continue
            return AuthorizationResult(status="allowed")
        return AuthorizationResult(status="denied", cause="no_matching_grant")


@dataclass(frozen=True)
class RepositoryResolution:
    authorized: bool
    repository_id: str
    cause: str = ""


class ConnectorRegistry(Protocol):
    def resolve_repository(
        self,
        principal: Principal,
        repository_id: str,
    ) -> RepositoryResolution: ...


class InMemoryConnectorRegistry:
    """Maps opaque repository IDs; rejects caller-supplied URLs and filesystem paths."""

    def __init__(self, admitted: Mapping[str, str]) -> None:
        self._admitted = dict(admitted)

    def resolve_repository(
        self,
        principal: Principal,
        repository_id: str,
    ) -> RepositoryResolution:
        _reject_untrusted_repository_selector(repository_id)
        canonical = self._admitted.get(repository_id)
        if canonical is None:
            return RepositoryResolution(
                authorized=False,
                repository_id=repository_id,
                cause="repository_not_registered",
            )
        return RepositoryResolution(authorized=True, repository_id=canonical)


class ReportAccess(Protocol):
    def read_report_bytes(self, tenant_id: str, job_id: str) -> bytes: ...


class CountingReportAccess:
    """Instrumentation wrapper: counts bytes read from the backing store."""

    def __init__(self, inner: ReportAccess) -> None:
        self._inner = inner
        self.bytes_read = 0

    def read_report_bytes(self, tenant_id: str, job_id: str) -> bytes:
        data = self._inner.read_report_bytes(tenant_id, job_id)
        self.bytes_read += len(data)
        return data

    def reset_read_count(self) -> None:
        self.bytes_read = 0


class InMemoryReportAccess:
    def __init__(self, reports: Mapping[tuple[str, str], bytes]) -> None:
        self._reports = dict(reports)

    def read_report_bytes(self, tenant_id: str, job_id: str) -> bytes:
        key = (tenant_id, job_id)
        if key not in self._reports:
            raise ServiceContractError("report_not_found", f"no report for job {job_id!r}")
        return self._reports[key]


def _reject_untrusted_repository_selector(repository_id: str) -> None:
    lowered = repository_id.lower()
    if repository_id.startswith(("/", "\\", ".")):
        raise ServiceContractError(
            "untrusted_repository_selector",
            "filesystem paths cannot authorize repository access",
        )
    if "://" in repository_id or lowered.startswith("file:"):
        raise ServiceContractError(
            "untrusted_repository_selector",
            "URLs cannot authorize repository access",
        )


_SUBMIT_REQUEST_FIELDS = frozenset(
    {
        "tenant_id",
        "repository_id",
        "base_tip",
        "comparison_base",
        "head_or_snapshot",
        "policy_origin",
        "scope_digest",
        "profile",
        "reviewer_digest",
        "request_kind",
    }
)
_ENVELOPE_FIELDS = frozenset({"api_version", "request"})


def decode_submit_envelope(raw: bytes) -> ServiceRequest:
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise ServiceContractError(
            "envelope_too_large",
            f"submit envelope exceeds {MAX_ENVELOPE_BYTES} bytes",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ServiceContractError("invalid_envelope", "submit envelope must be UTF-8") from err
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as err:
        raise ServiceContractError("invalid_envelope", f"malformed JSON: {err}") from err
    if not isinstance(obj, dict):
        raise ServiceContractError("invalid_envelope", "submit envelope root must be an object")
    unknown = set(obj) - _ENVELOPE_FIELDS
    if unknown:
        raise ServiceContractError(
            "unknown_envelope_fields",
            f"unknown envelope fields: {sorted(unknown)}",
        )
    version = obj.get("api_version")
    if version != API_ENVELOPE_VERSION:
        raise ServiceContractError(
            "unsupported_api_version",
            f"unsupported api_version {version!r}",
        )
    request_obj = obj.get("request")
    if not isinstance(request_obj, dict):
        raise ServiceContractError("invalid_request", "request must be an object")
    return decode_service_request(request_obj)


def decode_service_request(obj: Mapping[str, Any]) -> ServiceRequest:
    unknown = set(obj) - _SUBMIT_REQUEST_FIELDS
    if unknown:
        raise ServiceContractError(
            "unknown_request_fields",
            f"unknown request fields: {sorted(unknown)}",
        )
    required = _SUBMIT_REQUEST_FIELDS - {"request_kind"}
    missing = [name for name in sorted(required) if name not in obj]
    if missing:
        raise ServiceContractError(
            "missing_request_fields",
            f"missing request fields: {missing}",
        )
    request_kind = obj.get("request_kind", "full")
    if request_kind not in ("full", "patch_only"):
        raise ServiceContractError(
            "invalid_request_kind",
            f"unsupported request_kind {request_kind!r}",
        )
    tenant_id = _require_non_empty_str(obj, "tenant_id")
    repository_id = _require_non_empty_str(obj, "repository_id")
    _reject_untrusted_repository_selector(repository_id)
    return ServiceRequest(
        tenant_id=tenant_id,
        repository_id=repository_id,
        base_tip=_require_non_empty_str(obj, "base_tip"),
        comparison_base=_require_non_empty_str(obj, "comparison_base"),
        head_or_snapshot=_require_non_empty_str(obj, "head_or_snapshot"),
        policy_origin=_require_non_empty_str(obj, "policy_origin"),
        scope_digest=_require_non_empty_str(obj, "scope_digest"),
        profile=_require_non_empty_str(obj, "profile"),
        reviewer_digest=_require_non_empty_str(obj, "reviewer_digest"),
        request_kind=request_kind,
    )


def decode_report_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_REPORT_BYTES:
        raise ServiceContractError(
            "report_too_large",
            f"report exceeds {MAX_REPORT_BYTES} bytes",
        )
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ServiceContractError("invalid_report", f"malformed report JSON: {err}") from err
    if not isinstance(obj, dict):
        raise ServiceContractError("invalid_report", "report root must be an object")
    schema = obj.get("schema")
    if schema != "1":
        raise ServiceContractError("unsupported_report_schema", f"unsupported report schema {schema!r}")
    kind = obj.get("kind")
    if kind == "full":
        allowed = {
            "schema",
            "kind",
            "contract",
            "receipts",
            "inventory",
            "exclusions",
            "findings",
            "diagnostics",
            "execution",
        }
    elif kind == "limit_failure":
        allowed = {
            "schema",
            "kind",
            "known_inputs",
            "exit_code",
            "analysis_complete",
            "details_omitted",
            "cause",
            "limit",
            "omitted_domains",
        }
    else:
        raise ServiceContractError("invalid_report_kind", f"unknown report kind {kind!r}")
    unknown = set(obj) - allowed
    if unknown:
        raise ServiceContractError(
            "unknown_report_fields",
            f"unknown report fields: {sorted(unknown)}",
        )
    if kind == "limit_failure":
        if obj.get("exit_code") != 2:
            raise ServiceContractError("invalid_limit_failure", "limit_failure exit_code must be 2")
        if obj.get("analysis_complete") is not False:
            raise ServiceContractError(
                "invalid_limit_failure",
                "limit_failure analysis_complete must be false",
            )
    return obj


def encode_submit_envelope(request: ServiceRequest) -> bytes:
    body = {
        "api_version": API_ENVELOPE_VERSION,
        "request": service_request_to_dict(request),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def service_request_to_dict(request: ServiceRequest) -> dict[str, Any]:
    data: dict[str, Any] = {
        "tenant_id": request.tenant_id,
        "repository_id": request.repository_id,
        "base_tip": request.base_tip,
        "comparison_base": request.comparison_base,
        "head_or_snapshot": request.head_or_snapshot,
        "policy_origin": request.policy_origin,
        "scope_digest": request.scope_digest,
        "profile": request.profile,
        "reviewer_digest": request.reviewer_digest,
    }
    if request.request_kind != "full":
        data["request_kind"] = request.request_kind
    return data


def authorized_job_to_dict(job: AuthorizedJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "tenant_id": job.tenant_id,
        "repository_id": job.repository_id,
        "request_digest": job.request_digest,
        "state": job.state,
    }


def _require_non_empty_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise ServiceContractError("invalid_field", f"{key} must be a non-empty string")
    return value
