"""Fake/local identity authentication stubs (no live OIDC or cloud credentials)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping

from service.contracts import Principal, ServiceContractError


class IdentityError(ServiceContractError):
    """Assertion or policy violation during authentication."""


@dataclass(frozen=True)
class IdentityPolicy:
    issuer: str
    audience: str
    organization_bindings: Mapping[str, str]
    verification_keys: Mapping[str, str]
    provisioning_origin: str
    max_assertion_age_seconds: int = 300


@dataclass(frozen=True)
class AuthenticatedSubject:
    subject_id: str
    tenant_id: str
    email: str
    organization_id: str
    key_id: str


def authenticate(assertion: bytes, policy: IdentityPolicy, *, now: float | None = None) -> Principal:
    """
    Verify a bounded fake assertion envelope.

    Caller-supplied email, display name or tenant_id strings never grant organization
    membership; tenant binding comes only from organization_bindings under a verified issuer.
    """
    clock = now if now is not None else time.time()
    try:
        payload = json.loads(assertion.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise IdentityError("invalid_assertion", f"malformed assertion JSON: {err}") from err
    if not isinstance(payload, dict):
        raise IdentityError("invalid_assertion", "assertion root must be an object")
    issuer = _require_str(payload, "iss")
    audience = _require_str(payload, "aud")
    if issuer != policy.issuer:
        raise IdentityError("wrong_issuer", f"issuer {issuer!r} does not match policy")
    if audience != policy.audience:
        raise IdentityError("wrong_audience", f"audience {audience!r} does not match policy")
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise IdentityError("invalid_expiry", "exp must be a number")
    if clock >= float(exp):
        raise IdentityError("assertion_expired", "assertion is expired")
    iat = payload.get("iat")
    if isinstance(iat, (int, float)) and clock - float(iat) > policy.max_assertion_age_seconds:
        raise IdentityError("assertion_stale", "assertion exceeds max age")
    kid = _require_str(payload, "kid")
    if kid not in policy.verification_keys:
        raise IdentityError("unknown_verification_key", f"unknown key id {kid!r}")
    if policy.verification_keys[kid] == "revoked":
        raise IdentityError("verification_key_revoked", "verification key is revoked")
    org_id = _require_str(payload, "org_id")
    bound_tenant = policy.organization_bindings.get(org_id)
    if bound_tenant is None:
        raise IdentityError("organization_unbound", "organization is not bound to a tenant")
    _ = payload.get("email", "")
    claimed_tenant = payload.get("tenant_id")
    if isinstance(claimed_tenant, str) and claimed_tenant and claimed_tenant != bound_tenant:
        raise IdentityError(
            "tenant_binding_mismatch",
            "caller tenant_id does not match organization binding",
        )
    subject_id = _require_str(payload, "sub")
    grants_revision = _require_str(payload, "grants_revision")
    return Principal(
        tenant_id=bound_tenant,
        subject_id=subject_id,
        grants_revision=grants_revision,
    )


def encode_fake_assertion(
    *,
    policy: IdentityPolicy,
    subject_id: str,
    org_id: str,
    grants_revision: str,
    kid: str = "local-k1",
    email: str = "",
    tenant_id: str = "",
    ttl_seconds: int = 60,
    now: float | None = None,
) -> bytes:
    """Build a deterministic fake assertion for local tests only."""
    clock = now if now is not None else time.time()
    body: dict[str, Any] = {
        "iss": policy.issuer,
        "aud": policy.audience,
        "sub": subject_id,
        "org_id": org_id,
        "grants_revision": grants_revision,
        "kid": kid,
        "iat": int(clock),
        "exp": int(clock + ttl_seconds),
        "email": email,
    }
    if tenant_id:
        body["tenant_id"] = tenant_id
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _require_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise IdentityError("invalid_assertion", f"{key} must be a non-empty string")
    return value
