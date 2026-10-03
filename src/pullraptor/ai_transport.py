"""Bounded approved-address AI transport with injectable inert fixtures (E03-A2)."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import re
import time
import urllib.error
import urllib.request
from typing import Callable, Protocol

from pullraptor.ai_adapter import AIProposal
from pullraptor.ai_context import ContextSelection
from pullraptor.models import RecordLimits

_MAX_RESPONSE_BYTES = 1_048_576
_AUTHORITY_KEY = re.compile(
    r'"(support|permission|publication|destination|evidence|acceptance|merge)"\s*:',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProviderPolicy:
    profile: str
    approved_origin: str
    approved_path: str
    permitted_addresses: tuple[str, ...]
    credential_reference: str
    spend_cap: float | None
    retention_policy: str


@dataclass(frozen=True)
class AIBudget:
    max_requests: int
    context_bytes: int
    output_tokens: int
    deadline_seconds: float
    started_at: float


@dataclass(frozen=True)
class AIInvocationReceipt:
    requests_used: int
    context_bytes: int
    requested_output_tokens: int
    elapsed_seconds: float
    cost_state: str


@dataclass(frozen=True)
class AIResult:
    proposals: tuple[AIProposal, ...]
    receipt: AIInvocationReceipt
    state: str
    cause: str


@dataclass
class TransportAttempt:
    """Mutable ledger shared across retries within one invoke_provider call."""

    requests_used: int = 0
    context_bytes: int = 0
    requested_output_tokens: int = 0
    started_at: float = 0.0


@dataclass
class TransportSendRecord:
    sent_context_bytes: int = 0
    sent_credentials: bool = False
    outbound_requests: int = 0


class TransportConnector(Protocol):
    def connect(self, host: str, port: int) -> tuple[str, int]:
        """Return the actual connected peer host/port."""

    def post(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        *,
        timeout: float,
    ) -> tuple[int, bytes]:
        """Return HTTP status and response body bytes."""


def _empty_receipt(started: float) -> AIInvocationReceipt:
    return AIInvocationReceipt(0, 0, 0, max(0.0, time.monotonic() - started), "cost_unknown")


def _result(
    *,
    proposals: tuple[AIProposal, ...],
    attempt: TransportAttempt,
    started: float,
    state: str,
    cause: str,
) -> AIResult:
    elapsed = max(0.0, time.monotonic() - started)
    receipt = AIInvocationReceipt(
        requests_used=attempt.requests_used,
        context_bytes=attempt.context_bytes,
        requested_output_tokens=attempt.requested_output_tokens,
        elapsed_seconds=elapsed,
        cost_state="cost_unknown",
    )
    return AIResult(proposals=proposals, receipt=receipt, state=state, cause=cause)


def _parse_origin(origin: str) -> tuple[str, str, int]:
    if not origin.startswith("https://"):
        raise ValueError("approved_origin must use https")
    rest = origin[len("https://") :]
    if "/" in rest:
        host_port, _ = rest.split("/", 1)
    else:
        host_port = rest
    if host_port.startswith("["):
        end = host_port.index("]")
        host = host_port[1:end]
        port = 443
        if len(host_port) > end + 1 and host_port[end + 1] == ":":
            port = int(host_port[end + 2 :])
    elif ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = host_port, 443
    return "https", host, port


def _is_private_or_local(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address in {"localhost"} or address.endswith(".localhost")
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _validate_connected_peer(
    connected_host: str,
    policy: ProviderPolicy,
    record: TransportSendRecord,
) -> str | None:
    private = _is_private_or_local(connected_host)
    if policy.profile != "local" and private:
        return "remote_private_address_denied"
    if policy.profile == "local":
        if private or connected_host in policy.permitted_addresses or not policy.permitted_addresses:
            return None
        return "address_not_permitted"
    if policy.permitted_addresses and connected_host not in policy.permitted_addresses:
        return "connected_address_mismatch"
    return None


def _strict_decode_proposals(
    raw: bytes,
    *,
    model: str,
    limits: RecordLimits,
) -> tuple[tuple[AIProposal, ...], str | None]:
    if len(raw) > _MAX_RESPONSE_BYTES:
        return (), "response_too_large"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (), "invalid_json"
    if _AUTHORITY_KEY.search(raw.decode("utf-8", errors="replace")):
        return (), "authority_field_rejected"
    if not isinstance(payload, dict):
        return (), "invalid_shape"
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return (), "invalid_shape"
    if len(choices) > limits.max_aggregate_items:
        return (), "too_many_items"
    proposals: list[AIProposal] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content", "")
        if not isinstance(content, str):
            return (), "invalid_shape"
        if len(content.encode("utf-8")) > limits.max_string_bytes:
            return (), "proposal_too_large"
        proposals.append(
            AIProposal(
                kind="explanation",
                target_rule=None,
                target_span=None,
                content=content,
                model=model,
                tokens_used=0,
            )
        )
    return tuple(proposals), None


def _build_request_body(context_bytes: bytes, output_tokens: int, model: str) -> bytes:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": context_bytes.decode("utf-8", errors="replace")}],
        "max_tokens": output_tokens,
    }
    return json.dumps(payload).encode("utf-8")


class InertHttpsConnector:
    """Test double that records sends and returns a canned response."""

    def __init__(
        self,
        *,
        connected_host: str,
        connected_port: int = 443,
        status: int = 200,
        response_body: bytes = b'{"choices":[{"message":{"content":"ok"}}]}',
        record: TransportSendRecord | None = None,
    ) -> None:
        self.connected_host = connected_host
        self.connected_port = connected_port
        self.status = status
        self.response_body = response_body
        self.record = record or TransportSendRecord()

    def connect(self, host: str, port: int) -> tuple[str, int]:
        return self.connected_host, self.connected_port

    def post(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        *,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.record.outbound_requests += 1
        self.record.sent_context_bytes += len(body)
        self.record.sent_credentials = self.record.sent_credentials or bool(headers.get("Authorization"))
        return self.status, self.response_body


class UrllibConnector:
    """Production connector with redirects disabled and ambient proxies cleared."""

    def __init__(self, record: TransportSendRecord | None = None) -> None:
        self.record = record or TransportSendRecord()

    def connect(self, host: str, port: int) -> tuple[str, int]:
        return host, port

    def post(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        *,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.record.outbound_requests += 1
        self.record.sent_context_bytes += len(body)
        self.record.sent_credentials = self.record.sent_credentials or bool(headers.get("Authorization"))
        opener = urllib.request.build_opener(_NoRedirectHandler(), _NoProxyHandler())
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with opener.open(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200) or 200
                raw = resp.read(_MAX_RESPONSE_BYTES + 1)
                return status, raw
        except urllib.error.HTTPError as err:
            raw = err.read(_MAX_RESPONSE_BYTES + 1) if err.fp else b""
            return err.code, raw


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _NoProxyHandler(urllib.request.ProxyHandler):
    def __init__(self) -> None:
        super().__init__({})


def invoke_provider(
    context: ContextSelection,
    policy: ProviderPolicy,
    budget: AIBudget,
    *,
    credential: str = "",
    model: str = "default",
    connector: TransportConnector | None = None,
    send_record: TransportSendRecord | None = None,
    limits: RecordLimits | None = None,
    retry_on_failure: Callable[[], bool] | None = None,
) -> AIResult:
    """Send bounded context to an approved provider or inert test connector."""
    started = budget.started_at
    attempt = TransportAttempt(started_at=started)
    record = send_record or TransportSendRecord()
    lim = limits or RecordLimits()

    if context.state != "ok" or not context.serialized_bytes:
        return _result(proposals=(), attempt=attempt, started=started, state="unavailable", cause=context.cause or context.state)

    try:
        scheme, host, port = _parse_origin(policy.approved_origin)
    except ValueError:
        return _result(proposals=(), attempt=attempt, started=started, state="transport_denied", cause="invalid_origin")

    if scheme != "https":
        return _result(proposals=(), attempt=attempt, started=started, state="transport_denied", cause="non_https_origin")

    if not policy.approved_path.startswith("/"):
        return _result(proposals=(), attempt=attempt, started=started, state="transport_denied", cause="invalid_path")

    url = f"{policy.approved_origin.rstrip('/')}{policy.approved_path}"
    conn = connector or UrllibConnector(record=record)

    max_attempts = min(2, max(1, budget.max_requests))
    context_payload = context.serialized_bytes
    last_cause = "provider_error"

    for _ in range(max_attempts):
        if attempt.requests_used >= budget.max_requests:
            return _result(proposals=(), attempt=attempt, started=started, state="budget_exhausted", cause="max_requests")
        elapsed = time.monotonic() - started
        if elapsed >= budget.deadline_seconds:
            return _result(proposals=(), attempt=attempt, started=started, state="budget_exhausted", cause="deadline_exhausted")
        if attempt.context_bytes + len(context_payload) > budget.context_bytes:
            return _result(proposals=(), attempt=attempt, started=started, state="budget_exhausted", cause="context_budget_exhausted")

        connected_host, _ = conn.connect(host, port)
        deny = _validate_connected_peer(connected_host, policy, record)
        if deny:
            return _result(proposals=(), attempt=attempt, started=started, state="transport_denied", cause=deny)

        per_request_tokens = min(budget.output_tokens, 2048)
        body = _build_request_body(context_payload, per_request_tokens, model)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "PullRaptor-AITransport/0.3.0",
        }
        if credential and policy.credential_reference:
            headers["Authorization"] = f"Bearer {credential}"

        timeout = max(0.1, budget.deadline_seconds - (time.monotonic() - started))
        status, raw = conn.post(url, body, headers, timeout=timeout)
        attempt.requests_used += 1
        attempt.context_bytes += len(context_payload)
        attempt.requested_output_tokens += per_request_tokens

        if status in (301, 302, 303, 307, 308):
            return _result(proposals=(), attempt=attempt, started=started, state="transport_denied", cause="redirect_not_followed")

        if status >= 400:
            last_cause = "provider_error"
            if retry_on_failure and retry_on_failure() and attempt.requests_used < budget.max_requests:
                continue
            return _result(proposals=(), attempt=attempt, started=started, state="unavailable", cause=last_cause)

        proposals, decode_cause = _strict_decode_proposals(raw, model=model, limits=lim)
        if decode_cause:
            return _result(proposals=(), attempt=attempt, started=started, state="unavailable", cause=decode_cause)
        return _result(proposals=proposals, attempt=attempt, started=started, state="ok", cause="")

    return _result(proposals=(), attempt=attempt, started=started, state="unavailable", cause=last_cause)


def ignore_ambient_proxy_environment() -> dict[str, str | None]:
    """Return proxy-related environment keys cleared for transport construction."""
    keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    return {k: None for k in keys}
