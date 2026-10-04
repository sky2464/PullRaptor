"""Local secret-risk pattern scanning without value retention or remote probes."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable

_PRIVATE_KEY_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
)

_LABEL_RE = re.compile(
    rb"(?i)(api_key|access_token|client_secret)\s*[:=]\s*"
    rb"(?:'([^']{32,512})'|\"([^\"]{32,512})\"|([0-9A-Za-z_\-]{40,512}))"
)


@dataclass(frozen=True)
class SecretPattern:
    """Versioned local pattern identifier."""

    pattern_id: str
    version: str
    context_class: str = "local_shape"


@dataclass(frozen=True)
class RelativeSpan:
    """Byte offsets in the scanned source blob."""

    start_byte: int
    end_byte: int


@dataclass(frozen=True)
class SecretObservation:
    """Value-free secret-risk observation."""

    pattern_id: str
    version: str
    relative_span: RelativeSpan
    redacted_label: str
    context_class: str


DEFAULT_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern(pattern_id="SECRET001", version="1", context_class="private_key_header"),
    SecretPattern(pattern_id="SECRET002", version="1", context_class="labelled_assignment"),
    SecretPattern(pattern_id="SECRET003", version="1", context_class="labelled_entropy"),
)


def _shannon_bits_per_char(value: bytes) -> float:
    if not value:
        return 0.0
    counts: dict[int, int] = {}
    for byte in value:
        counts[byte] = counts.get(byte, 0) + 1
    length = len(value)
    entropy = 0.0
    for count in counts.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
    return entropy


def _append_unique(observations: list[SecretObservation], candidate: SecretObservation) -> None:
    for existing in observations:
        if (
            existing.pattern_id == candidate.pattern_id
            and existing.relative_span.start_byte == candidate.relative_span.start_byte
            and existing.relative_span.end_byte == candidate.relative_span.end_byte
        ):
            return
    observations.append(candidate)


def _scan_private_keys(source: bytes, pattern: SecretPattern, out: list[SecretObservation]) -> None:
    for marker in _PRIVATE_KEY_MARKERS:
        start = 0
        while True:
            idx = source.find(marker, start)
            if idx < 0:
                break
            span = RelativeSpan(start_byte=idx, end_byte=idx + len(marker))
            _append_unique(
                out,
                SecretObservation(
                    pattern_id=pattern.pattern_id,
                    version=pattern.version,
                    relative_span=span,
                    redacted_label="[REDACTED PRIVATE KEY HEADER]",
                    context_class=pattern.context_class,
                ),
            )
            start = idx + 1


def _scan_labelled(source: bytes, patterns: Iterable[SecretPattern], out: list[SecretObservation]) -> None:
    pattern_by_id = {item.pattern_id: item for item in patterns}
    secret002 = pattern_by_id.get("SECRET002")
    secret003 = pattern_by_id.get("SECRET003")
    for match in _LABEL_RE.finditer(source):
        label = match.group(1).decode("ascii", errors="replace").lower()
        quoted_single = match.group(2)
        quoted_double = match.group(3)
        bare = match.group(4)
        if quoted_single is not None:
            value = quoted_single
            value_start = match.start(2)
        elif quoted_double is not None:
            value = quoted_double
            value_start = match.start(3)
        elif bare is not None:
            value = bare
            value_start = match.start(4)
        else:
            continue
        value_end = value_start + len(value)
        redacted = f"[REDACTED {label}]"
        if secret002 is not None and (quoted_single is not None or quoted_double is not None):
            if 32 <= len(value) <= 512 and re.fullmatch(rb"[0-9A-Za-z_\-]+", value):
                _append_unique(
                    out,
                    SecretObservation(
                        pattern_id=secret002.pattern_id,
                        version=secret002.version,
                        relative_span=RelativeSpan(value_start, value_end),
                        redacted_label=redacted,
                        context_class=secret002.context_class,
                    ),
                )
        if secret003 is not None and 40 <= len(value) <= 512:
            if _shannon_bits_per_char(value) >= 4.0:
                _append_unique(
                    out,
                    SecretObservation(
                        pattern_id=secret003.pattern_id,
                        version=secret003.version,
                        relative_span=RelativeSpan(value_start, value_end),
                        redacted_label=f"[REDACTED ENTROPY {label}]",
                        context_class=secret003.context_class,
                    ),
                )


def scan_secrets(
    source: bytes,
    patterns: tuple[SecretPattern, ...] = DEFAULT_PATTERNS,
) -> tuple[SecretObservation, ...]:
    """Scan local source bytes for configured secret-risk shapes."""
    observations: list[SecretObservation] = []
    for pattern in patterns:
        if pattern.pattern_id == "SECRET001":
            _scan_private_keys(source, pattern, observations)
    _scan_labelled(source, patterns, observations)
    observations.sort(key=lambda item: (item.relative_span.start_byte, item.pattern_id))
    return tuple(observations)
