"""Optional language worker contracts and coordinator validation (E04-A1)."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from pullraptor.models import Deadline, Limits, ProcessBounds, encode_record
from pullraptor.process import run_bounded

LANGUAGE_WORKER_PROTOCOL = "pullraptor_language_worker_v1"


@dataclass(frozen=True)
class LanguageRegistryEntry:
    language: str
    capability: str
    executable_argv: tuple[str, ...]
    executable_digest: str
    grammar_digest: str
    allowed_environment: tuple[tuple[str, str], ...]
    worker_cwd: str


@dataclass(frozen=True)
class LanguageRegistry:
    entries: tuple[LanguageRegistryEntry, ...]


@dataclass(frozen=True)
class LanguageRequest:
    contract_digest: str
    scope_keys: tuple[str, ...]
    language: str
    grammar_digest: str
    capability: str
    source_blobs: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class LanguageResult:
    contract_digest: str
    completed_keys: tuple[str, ...]
    content_facts: tuple[dict[str, object], ...]
    unsupported: tuple[str, ...]
    producer_digest: str


def digest_executable_script(argv: tuple[str, ...]) -> str:
    """Return SHA-256 hex digest of the trusted worker script path (last argv element)."""
    script = Path(argv[-1])
    return hashlib.sha256(script.read_bytes()).hexdigest()


def find_registry_entry(
    registry: LanguageRegistry,
    *,
    language: str,
    capability: str,
) -> LanguageRegistryEntry | None:
    for entry in registry.entries:
        if entry.language == language and entry.capability == capability:
            return entry
    return None


def validate_worker_result(request: LanguageRequest, raw: LanguageResult) -> LanguageResult:
    """Reject worker claims that omit scope, advertise extra capability, or mismatch contract."""
    unsupported: list[str] = list(raw.unsupported)
    completed = set(raw.completed_keys)

    if raw.contract_digest != request.contract_digest:
        unsupported.append("contract_mismatch")

    for key in request.scope_keys:
        if key not in completed:
            unsupported.append("missing_receipt")

    if raw.producer_digest != request.grammar_digest:
        unsupported.append("grammar_config_change")

    advertised_caps = {
        str(fact.get("capability"))
        for fact in raw.content_facts
        if isinstance(fact, dict) and fact.get("capability") is not None
    }
    for cap in advertised_caps:
        if cap not in ("syntax", "structure", request.capability):
            unsupported.append("extra_capability")

    for key in completed:
        if key not in request.scope_keys:
            unsupported.append("foreign_receipt")

    cleaned_completed = tuple(
        k for k in raw.completed_keys if k in request.scope_keys and "missing_receipt" not in unsupported
    )
    return LanguageResult(
        contract_digest=raw.contract_digest,
        completed_keys=cleaned_completed,
        content_facts=raw.content_facts,
        unsupported=tuple(sorted(set(unsupported))),
        producer_digest=raw.producer_digest,
    )


def _worker_environment(entry: LanguageRegistryEntry) -> dict[str, str]:
    return {key: value for key, value in entry.allowed_environment}


def _serialize_worker_request(request: LanguageRequest, limits: Limits) -> bytes:
    source_blobs = [
        [path, base64.b64encode(blob).decode("ascii")]
        for path, blob in request.source_blobs
    ]
    payload = {
        "protocol": LANGUAGE_WORKER_PROTOCOL,
        "contract_digest": request.contract_digest,
        "scope_keys": list(request.scope_keys),
        "language": request.language,
        "grammar_digest": request.grammar_digest,
        "capability": request.capability,
        "source_blobs": source_blobs,
    }
    return encode_record(payload, limits.record_limits)


def _language_result_from_payload(obj: dict[str, object]) -> LanguageResult:
    if obj.get("protocol") != LANGUAGE_WORKER_PROTOCOL:
        raise ValueError("unexpected language worker protocol")

    completed_raw = obj.get("completed_keys", ())
    unsupported_raw = obj.get("unsupported", ())
    facts_raw = obj.get("content_facts", ())

    if not isinstance(completed_raw, list):
        raise ValueError("completed_keys must be a list")
    if not isinstance(unsupported_raw, list):
        raise ValueError("unsupported must be a list")
    if not isinstance(facts_raw, list):
        raise ValueError("content_facts must be a list")

    content_facts: list[dict[str, object]] = []
    for item in facts_raw:
        if not isinstance(item, dict):
            raise ValueError("content_facts entries must be objects")
        content_facts.append(item)

    return LanguageResult(
        contract_digest=str(obj.get("contract_digest", "")),
        completed_keys=tuple(str(k) for k in completed_raw),
        content_facts=tuple(content_facts),
        unsupported=tuple(str(u) for u in unsupported_raw),
        producer_digest=str(obj.get("producer_digest", "")),
    )


def _decode_worker_stdout(stdout: bytes, limits: Limits) -> LanguageResult:
    from pullraptor.models import decode_record

    if not stdout:
        raise ValueError("empty worker stdout")
    obj = decode_record(stdout, "language_worker_result", limits.record_limits)
    return _language_result_from_payload(obj)


def run_language(
    request: LanguageRequest,
    *,
    registry: LanguageRegistry,
    limits: Limits,
    deadline: Deadline,
) -> LanguageResult:
    """Dispatch a bounded stdin JSON request to a trusted registry worker and validate receipts."""
    entry = find_registry_entry(registry, language=request.language, capability=request.capability)
    if entry is None:
        gap = LanguageResult(request.contract_digest, (), (), ("registry_miss",), request.grammar_digest)
        return validate_worker_result(request, gap)

    if entry.grammar_digest != request.grammar_digest:
        gap = LanguageResult(
            request.contract_digest,
            (),
            (),
            ("grammar_registry_mismatch",),
            request.grammar_digest,
        )
        return validate_worker_result(request, gap)

    try:
        actual_digest = digest_executable_script(entry.executable_argv)
    except OSError:
        gap = LanguageResult(request.contract_digest, (), (), ("registry_executable_unavailable",), entry.grammar_digest)
        return validate_worker_result(request, gap)

    if actual_digest != entry.executable_digest:
        gap = LanguageResult(
            request.contract_digest,
            (),
            (),
            ("registry_executable_digest_mismatch",),
            entry.grammar_digest,
        )
        return validate_worker_result(request, gap)

    try:
        input_bytes = _serialize_worker_request(request, limits)
    except ValueError:
        gap = LanguageResult(request.contract_digest, (), (), ("request_limit_exceeded",), entry.grammar_digest)
        return validate_worker_result(request, gap)

    bounds = ProcessBounds(
        max_stdout_bytes=limits.record_limits.max_payload_bytes,
        max_stderr_bytes=limits.max_stderr_bytes,
        timeout_seconds=limits.parse_timeout_seconds,
    )

    proc = run_bounded(
        entry.executable_argv,
        cwd=Path(entry.worker_cwd),
        env=_worker_environment(entry),
        deadline=deadline,
        bounds=bounds,
        input_bytes=input_bytes,
        max_input_bytes=limits.record_limits.max_payload_bytes,
    )

    if proc.timed_out or proc.stdout_truncated or proc.stderr_truncated:
        gap = LanguageResult(request.contract_digest, (), (), ("timeout",), entry.grammar_digest)
        return validate_worker_result(request, gap)

    if proc.returncode != 0:
        gap = LanguageResult(
            request.contract_digest,
            (),
            (),
            ("worker_exit",),
            entry.grammar_digest,
        )
        return validate_worker_result(request, gap)

    try:
        raw = _decode_worker_stdout(proc.stdout, limits)
    except ValueError:
        gap = LanguageResult(
            request.contract_digest,
            (),
            (),
            ("worker_protocol_error",),
            entry.grammar_digest,
        )
        return validate_worker_result(request, gap)

    return validate_worker_result(request, raw)
