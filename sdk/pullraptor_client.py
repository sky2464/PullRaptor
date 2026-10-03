"""Thin owned SDK for the local /v1 review service (no kernel imports)."""

from __future__ import annotations

import json
from typing import Any

from service.api import ReviewService, job_response
from service.contracts import (
    AuthorizedJob,
    Principal,
    ServiceRequest,
    decode_report_bytes,
    decode_submit_envelope,
    encode_submit_envelope,
)


class PullRaptorClient:
    """In-process client over injected ReviewService handlers."""

    def __init__(self, service: ReviewService, principal: Principal) -> None:
        self._service = service
        self._principal = principal

    @property
    def principal(self) -> Principal:
        return self._principal

    def submit(self, request: ServiceRequest) -> dict[str, Any]:
        job = self._service.submit(request, self._principal)
        return job_response(job)

    def submit_bytes(self, envelope: bytes) -> dict[str, Any]:
        request = decode_submit_envelope(envelope)
        return self.submit(request)

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self._service.get_job(job_id, self._principal)
        return job_response(job)

    def get_report(self, job_id: str) -> dict[str, Any]:
        return self._service.get_report(job_id, self._principal)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self._service.cancel(job_id, self._principal)
        return job_response(job)

    def capabilities(self) -> dict[str, Any]:
        doc = self._service.capabilities(self._principal)
        return {"api_version": self._service.api_version(), "capabilities": doc.to_dict()}

    def roundtrip_report(self, job_id: str) -> dict[str, Any]:
        report = self.get_report(job_id)
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return decode_report_bytes(encoded)


def request_from_dict(data: dict[str, Any]) -> ServiceRequest:
    from service.contracts import decode_service_request

    return decode_service_request(data)


def encode_request(request: ServiceRequest) -> bytes:
    return encode_submit_envelope(request)


def decode_job(payload: dict[str, Any]) -> AuthorizedJob:
    job_obj = payload.get("job")
    if not isinstance(job_obj, dict):
        raise ValueError("job payload missing")
    return AuthorizedJob(
        job_id=job_obj["job_id"],
        tenant_id=job_obj["tenant_id"],
        repository_id=job_obj["repository_id"],
        request_digest=job_obj["request_digest"],
        state=job_obj["state"],
    )


def capability_rows(doc: CapabilityDocument) -> list[tuple[str, str, str]]:
    return list(doc.admitted_rows)
