"""Pinned AI context manifests and deterministic selection (E03-A1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from pullraptor.ai_adapter import redact_sensitive_content

_MAX_BLOCK_BYTES = 65_536


@dataclass(frozen=True)
class ContextBlock:
    id: str
    kind: str
    producer: str
    source_revision: str
    digest: str
    serialized_bytes: bytes
    mandatory: bool
    priority: int


@dataclass(frozen=True)
class ContextManifest:
    report_digest: str
    head: str
    blocks: tuple[ContextBlock, ...]
    retrieval_receipts: tuple[str, ...]


@dataclass(frozen=True)
class ContextSelection:
    block_ids: tuple[str, ...]
    serialized_bytes: bytes
    state: str
    cause: str


def block_digest(serialized: bytes) -> str:
    return hashlib.sha256(serialized).hexdigest()


def _ci_receipt_matches_head(receipt: str, head: str) -> bool:
    try:
        payload = json.loads(receipt)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("head") == head


def select_context(manifest: ContextManifest, budget_bytes: int) -> ContextSelection:
    """Select context blocks under an exact byte budget with mandatory-first ordering."""
    if budget_bytes <= 0:
        return ContextSelection((), b"", "unavailable", "non_positive_budget")

    admitted: list[ContextBlock] = []
    for block in manifest.blocks:
        if block.kind == "ci_log":
            matched = any(_ci_receipt_matches_head(r, manifest.head) for r in manifest.retrieval_receipts)
            if not matched:
                continue
        if block.kind == "issue" and block.source_revision != manifest.report_digest:
            continue
        if block_digest(block.serialized_bytes) != block.digest:
            continue
        if len(block.serialized_bytes) > _MAX_BLOCK_BYTES:
            if block.mandatory:
                return ContextSelection((), b"", "unavailable", "mandatory_context_over_budget")
            continue
        admitted.append(block)

    mandatory = sorted([b for b in admitted if b.mandatory], key=lambda b: (b.priority, b.id))
    for block in mandatory:
        if len(block.serialized_bytes) > budget_bytes:
            return ContextSelection((), b"", "unavailable", "mandatory_context_over_budget")

    selected: list[ContextBlock] = []
    used = 0
    for block in mandatory:
        selected.append(block)
        used += len(block.serialized_bytes)

    optional = sorted([b for b in admitted if not b.mandatory], key=lambda b: (b.priority, b.id))
    for block in optional:
        if used + len(block.serialized_bytes) > budget_bytes:
            break
        selected.append(block)
        used += len(block.serialized_bytes)

    payload = b"".join(b.serialized_bytes for b in selected)
    return ContextSelection(
        tuple(b.id for b in selected),
        payload,
        "ok" if selected else "unavailable",
        "" if selected else "no_admitted_blocks",
    )


def preview_context(selection: ContextSelection) -> str:
    """Return a redacted human-readable preview of selected context bytes."""
    text = selection.serialized_bytes.decode("utf-8", errors="replace")
    return redact_sensitive_content(text)


_AUTHORITY_FIELD = re.compile(r'"(support|permission|publication|destination)"\s*:', re.IGNORECASE)


def injected_config_inert(config_blob: str) -> bool:
    """True when untrusted config text contains no authority-like JSON keys."""
    return _AUTHORITY_FIELD.search(config_blob) is None
