"""Optional language worker contracts and coordinator validation (E04-A1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageRegistryEntry:
    language: str
    capability: str
    executable_digest: str
    grammar_digest: str
    allowed_environment: tuple[tuple[str, str], ...]


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
