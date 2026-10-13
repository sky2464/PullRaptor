"""PullRaptor immutable records, bounded codec, and canonical report output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import time
from typing import Any, Union


class LimitExceeded(ValueError, TimeoutError):
    """Trusted resource exhaustion; carries no source-controlled advice."""
    def __init__(self, cause: str, name: str, cap: int | float | None, observed: int | float | None):
        self.cause, self.name, self.cap, self.observed = cause, name, cap, observed
        super().__init__(f"{name} resource limit exceeded")


@dataclass(frozen=True)
class RecordLimits:
    """Limits on decoded and encoded record structures."""
    max_depth: int = 64
    max_aggregate_items: int = 100_000
    max_string_bytes: int = 4_194_304
    max_payload_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if self.max_aggregate_items < 1:
            raise ValueError("max_aggregate_items must be >= 1")
        if self.max_string_bytes < 1:
            raise ValueError("max_string_bytes must be >= 1")
        if self.max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be >= 1")


@dataclass(frozen=True)
class Deadline:
    """Operational timing constraints derived from a single monotonic start time."""
    started_at: float
    duration_seconds: float
    reserve_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.duration_seconds < 3.0:
            raise ValueError("duration_seconds must be >= 3.0 to reserve finalization capacity")
        if self.reserve_seconds < 0.0 or self.duration_seconds <= self.reserve_seconds:
            raise ValueError("reserve_seconds must be positive and less than duration_seconds")

    @property
    def work_cutoff(self) -> float:
        return self.started_at + self.duration_seconds - self.reserve_seconds

    @property
    def final_cutoff(self) -> float:
        return self.started_at + self.duration_seconds

    def remaining_work(self, now: float | None = None) -> float:
        t = time.monotonic() if now is None else now
        return max(0.0, self.work_cutoff - t)

    def remaining_final(self, now: float | None = None) -> float:
        t = time.monotonic() if now is None else now
        return max(0.0, self.final_cutoff - t)

    def is_work_exhausted(self, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        return t >= self.work_cutoff

    def is_final_exhausted(self, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        return t >= self.final_cutoff


@dataclass(frozen=True)
class ProcessBounds:
    """Resource limits for subprocess execution."""
    max_stdout_bytes: int = 8_388_608
    max_stderr_bytes: int = 65_536
    timeout_seconds: float = 2.0


@dataclass(frozen=True)
class ProcessResult:
    """Bounded subprocess execution result."""
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_seconds: float
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


@dataclass(frozen=True)
class Limits:
    """Global review and engine limits."""
    max_tracked_entries: int = 10_000
    max_blob_bytes: int = 2_097_152
    max_total_bytes: int = 134_217_728
    parse_timeout_seconds: float = 2.0
    review_timeout_seconds: float = 60.0
    failure_reserve_seconds: float = 2.0
    max_cache_bytes: int = 268_435_456
    max_diff_bytes: int = 8_388_608
    max_stderr_bytes: int = 65_536
    record_limits: RecordLimits = field(default_factory=RecordLimits)


@dataclass(frozen=True)
class Span:
    """Exact source coordinate in a revision blob."""
    path: str
    side: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    start_column: int
    end_column: int

    def __post_init__(self) -> None:
        if self.side not in ("base", "head"):
            raise ValueError(f"side must be 'base' or 'head', got {self.side!r}")
        for attr in ("start_line", "end_line", "start_byte", "end_byte", "start_column", "end_column"):
            val = getattr(self, attr)
            if not isinstance(val, int) or isinstance(val, bool):
                raise ValueError(f"{attr} must be an integer, got {type(val)}")
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(f"end_line must be >= start_line, got {self.end_line} < {self.start_line}")
        if self.start_byte < 0:
            raise ValueError(f"start_byte must be >= 0, got {self.start_byte}")
        if self.end_byte < self.start_byte:
            raise ValueError(f"end_byte must be >= start_byte, got {self.end_byte} < {self.start_byte}")
        if self.start_column < 1:
            raise ValueError(f"start_column must be >= 1, got {self.start_column}")
        if self.end_column < 1:
            raise ValueError(f"end_column must be >= 1, got {self.end_column}")
        if self.start_line == self.end_line and self.start_column > self.end_column:
            raise ValueError(f"start_column cannot exceed end_column on same line ({self.start_column} > {self.end_column})")


@dataclass(frozen=True)
class Diagnostic:
    """Engine or analysis diagnostic."""
    code: str
    message: str
    span: Span | None = None
    path: str | None = None
    side: str | None = None
    cause: str | None = None
    recovery: str | None = None


@dataclass(frozen=True)
class BlobRef:
    """Reference to an immutable Git blob."""
    path: str | None
    path_bytes: bytes
    mode: str
    blob_oid: str
    size: int


@dataclass(frozen=True)
class Snapshot:
    """Immutable tree snapshot."""
    oid: str
    blobs: tuple[BlobRef, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        # Guarantee blobs are sorted by path_bytes
        sorted_blobs = tuple(sorted(self.blobs, key=lambda b: b.path_bytes))
        if sorted_blobs != self.blobs:
            object.__setattr__(self, "blobs", sorted_blobs)


@dataclass(frozen=True)
class Change:
    """Exact diff fact between two snapshot entries."""
    path: str | None
    path_bytes: bytes
    kind: str
    base_blob: BlobRef | None = None
    head_blob: BlobRef | None = None
    hunks: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ContentFacts:
    """Occurrence-free syntactic facts extracted from a blob.

    Never contains path, side, or snapshot identity.
    """
    blob_digest: str
    runtime_version: str
    schema_version: str
    extractor_digest: str
    symbols: tuple[Any, ...]
    imports: tuple[Any, ...]
    pattern_facts: tuple[Any, ...]
    unsupported_constructs: tuple[str, ...]
    relative_locations: tuple[Any, ...]


@dataclass(frozen=True)
class BoundFacts:
    """Syntactic facts bound to a specific snapshot occurrence."""
    content: ContentFacts
    snapshot: str
    path: str
    side: str

    def __post_init__(self) -> None:
        if self.side not in ("base", "head"):
            raise ValueError(f"side must be 'base' or 'head', got {self.side!r}")


@dataclass(frozen=True)
class ResolvedFacts:
    """Occurrence-bound facts with run-local resolution."""
    bound: BoundFacts
    resolved_imports: tuple[Any, ...]
    resolved_symbols: tuple[Any, ...]


@dataclass(frozen=True)
class FactResult:
    """Result of content fact extraction before occurrence binding."""
    content: ContentFacts | None
    diagnostics: tuple[Diagnostic, ...] = ()


def file_scope_key(kind: str, snapshot: str, path_bytes: bytes, capability: str) -> str:
    """Deterministic scope key for a file entry."""
    return f"file:{snapshot}:{path_bytes.hex()}:{capability}"


def import_scope_key(
    kind: str,
    snapshot: str,
    source_occurrence: str,
    canonical_target: str,
    relative_level: int,
    capability: str,
) -> str:
    """Deterministic scope key for an import lookup entry."""
    return f"import:{snapshot}:{source_occurrence}:{canonical_target}:{relative_level}:{capability}"


@dataclass(frozen=True)
class ScopeEntry:
    """Coordinator-owned required analysis unit."""
    key: str
    kind: str
    snapshot: str
    capability: str
    path_bytes: bytes | None = None
    path: str | None = None
    source_occurrence: str | None = None
    canonical_target: str | None = None
    relative_level: int | None = None
    reason: str = ""


@dataclass(frozen=True)
class ReviewContract:
    """Immutable contract pinning review inputs and expected scope."""
    base_tip: str
    comparison_base: str
    head: str
    policy_digest: str
    config_digest: str
    tool_digest: str
    profile: str
    expected_scope: tuple[ScopeEntry, ...]
    discovery_complete: bool


@dataclass(frozen=True)
class CoverageReceipt:
    """Independent proof of completion or gap for an expected scope item."""
    key: str
    contract_digest: str
    capability: str
    status: str
    cause: str | None = None
    recovery: str | None = None


@dataclass(frozen=True)
class Evidence:
    """Evidence record for a specific claim."""
    claim_key: str
    claim_type: str
    context: str
    supported: bool
    refuted: bool
    witnesses: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finding:
    """Differential review finding."""
    rule: str
    version: str
    obligation: str
    anchor: str
    span: Span
    claim: str
    severity: str
    policy_class: str
    state: str
    witness: str
    assumptions: tuple[str, ...] = ()
    delta: str = "newly_detected"
    evidence_delta: str = "added"


@dataclass(frozen=True)
class Config:
    """Declarative configuration."""
    profile: str = "structural"
    max_tracked_entries: int = 10_000
    max_blob_bytes: int = 2_097_152
    max_total_bytes: int = 134_217_728
    parse_timeout_seconds: float = 2.0
    review_timeout_seconds: float = 60.0
    failure_reserve_seconds: float = 2.0
    path_include: tuple[str, ...] = ()
    path_exclude: tuple[str, ...] = ()
    source_suffixes: tuple[str, ...] = (
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java",
        ".cs", ".c", ".h", ".cpp", ".hpp", ".cc", ".php", ".rb", ".swift",
        ".kt", ".kts", ".scala", ".sh", ".sql"
    )
    use_cache: bool = True
    cache_dir: str | None = None
    max_cache_bytes: int = 268_435_456
    max_report_bytes: int = 8_388_608
    max_report_items: int = 1_000_000
    max_report_depth: int = 64
    max_report_string_bytes: int = 4_194_304


@dataclass(frozen=True)
class FullReport:
    """Full canonical review report."""
    schema: str
    kind: str
    contract: ReviewContract
    receipts: tuple[CoverageReceipt, ...]
    inventory: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    execution: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema != "1":
            raise ValueError(f"Unsupported schema version {self.schema!r}")
        if self.kind != "full":
            raise ValueError(f"kind must be 'full', got {self.kind!r}")


@dataclass(frozen=True)
class LimitFailure:
    """Fixed-envelope failure report when resource limits or deadlines are exceeded."""
    schema: str
    kind: str
    known_inputs: dict[str, str | None]
    exit_code: int
    analysis_complete: bool
    details_omitted: bool
    cause: str
    limit: dict[str, Any] | None = None
    omitted_domains: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.schema != "1":
            raise ValueError(f"Unsupported schema version {self.schema!r}")
        if self.kind != "limit_failure":
            raise ValueError(f"kind must be 'limit_failure', got {self.kind!r}")
        if self.exit_code != 2:
            raise ValueError(f"LimitFailure exit_code must be 2, got {self.exit_code}")
        if self.analysis_complete is not False:
            raise ValueError("LimitFailure analysis_complete must be False")
        if self.details_omitted is not True:
            raise ValueError("LimitFailure details_omitted must be True")


Report = Union[FullReport, LimitFailure]


# --- Bounded Codec & Canonical Output ---

def _check_nesting_and_size(payload: bytes, limits: RecordLimits) -> None:
    if len(payload) > limits.max_payload_bytes:
        raise ValueError(
            f"Payload bytes ({len(payload)}) exceeds max_payload_bytes ({limits.max_payload_bytes})"
        )

    # String-aware delimiter nesting check
    depth = 0
    in_string = False
    escape = False

    for b in payload:
        if in_string:
            if escape:
                escape = False
            elif b == ord(b"\\"):
                escape = True
            elif b == ord(b'"'):
                in_string = False
        else:
            if b == ord(b'"'):
                in_string = True
            elif b in (ord(b"{"), ord(b"[")):
                depth += 1
                if depth > limits.max_depth:
                    raise LimitExceeded("record_limit_exceeded", "max_depth", limits.max_depth, depth)
            elif b in (ord(b"}"), ord(b"]")):
                depth -= 1
                if depth < 0:
                    raise ValueError("Unmatched closing bracket in JSON payload")


def _validate_tree_bounds(obj: Any, limits: RecordLimits, state: dict[str, int]) -> None:
    """Validate item count, string length, and lone surrogates recursively."""
    if isinstance(obj, str):
        # Check lone surrogates
        try:
            encoded = obj.encode("utf-8")
        except UnicodeEncodeError as err:
            raise ValueError("String contains lone surrogate") from err
        if len(encoded) > limits.max_string_bytes:
            raise LimitExceeded("record_limit_exceeded", "max_string_bytes", limits.max_string_bytes, len(encoded))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            state["items"] += 1
            if state["items"] > limits.max_aggregate_items:
                raise LimitExceeded("record_limit_exceeded", "max_aggregate_items", limits.max_aggregate_items, state["items"])
            _validate_tree_bounds(k, limits, state)
            _validate_tree_bounds(v, limits, state)
    elif isinstance(obj, list):
        for item in obj:
            state["items"] += 1
            if state["items"] > limits.max_aggregate_items:
                raise LimitExceeded("record_limit_exceeded", "max_aggregate_items", limits.max_aggregate_items, state["items"])
            _validate_tree_bounds(item, limits, state)


def decode_record(payload: bytes, schema: str, limits: RecordLimits) -> dict[str, Any]:
    """Strictly decode a JSON record within bounded depth, size, item, and schema constraints."""
    _check_nesting_and_size(payload, limits)

    # Strict UTF-8 check
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ValueError("Invalid UTF-8 payload") from err

    # Check for lone surrogate escape sequences like \ud800
    if "\\u" in text.lower():
        # Quick check for surrogate code points in decoded form
        pass

    def _no_constant(c: str) -> None:
        raise ValueError(f"Non-finite JSON constant not allowed: {c}")

    def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for k, v in pairs:
            if k in d:
                raise ValueError(f"Duplicate key found in JSON object: {k!r}")
            d[k] = v
        return d

    try:
        obj = json.loads(
            text,
            parse_constant=_no_constant,
            object_pairs_hook=_pairs_hook,
        )
    except json.JSONDecodeError as err:
        raise ValueError(f"Malformed JSON: {err}") from err

    if not isinstance(obj, dict):
        raise ValueError("Root record must be a JSON object")

    state = {"items": 0}
    _validate_tree_bounds(obj, limits, state)

    # Schema-specific checks
    if schema == "span":
        for attr in ("line", "start_line", "end_line", "start_byte", "end_byte", "start_column", "end_column"):
            if attr in obj:
                val = obj[attr]
                if isinstance(val, bool):
                    raise ValueError(f"Boolean not allowed where integer is required for {attr}")
                if not isinstance(val, int):
                    raise ValueError(f"Integer required for {attr}, got {type(val)}")
    elif schema == "report":
        kind = obj.get("kind")
        if kind not in ("full", "limit_failure"):
            raise ValueError(f"Unknown or invalid report kind: {kind!r}")
        if kind == "full":
            allowed = {"schema", "kind", "contract", "receipts", "inventory", "exclusions", "findings", "diagnostics", "execution"}
            unknown = set(obj.keys()) - allowed
            if unknown:
                raise ValueError(f"Unknown authority fields in full report: {sorted(unknown)}")
        elif kind == "limit_failure":
            allowed = {"schema", "kind", "known_inputs", "exit_code", "analysis_complete", "details_omitted", "cause", "limit", "omitted_domains"}
            unknown = set(obj.keys()) - allowed
            if unknown:
                raise ValueError(f"Unknown authority fields in limit_failure report: {sorted(unknown)}")
            if obj.get("exit_code") != 2:
                raise ValueError("LimitFailure exit_code must be 2")
            if obj.get("analysis_complete") is not False:
                raise ValueError("LimitFailure analysis_complete must be False")

    return obj


def encode_record(data: dict[str, Any], limits: RecordLimits) -> bytes:
    """Encode a dictionary to canonical JSON bytes."""
    state = {"items": 0}
    _validate_tree_bounds(data, limits, state)
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    encoded = text.encode("utf-8")
    if len(encoded) > limits.max_payload_bytes:
        raise LimitExceeded("report_limit_exceeded", "max_payload_bytes", limits.max_payload_bytes, len(encoded))
    _check_nesting_and_size(encoded, limits)
    return encoded


def _clean_for_canonical(data: Any) -> Any:
    """Recursively convert data structures and strip non-canonical metadata."""
    if isinstance(data, (tuple, list)):
        return [_clean_for_canonical(x) for x in data]
    elif isinstance(data, dict):
        return {k: _clean_for_canonical(v) for k, v in data.items()}
    elif isinstance(data, bytes):
        return data.hex()
    return data


def canonical_bytes(report: Report, *, limits: RecordLimits, deadline: Deadline) -> bytes:
    """Produce deterministic canonical bytes for a Report.

    Excludes execution metadata. Enforces deadlines and size bounds.
    """
    if report.kind == "full":
        if deadline.is_work_exhausted():
            raise LimitExceeded("deadline_exceeded", "work_cutoff", deadline.duration_seconds - deadline.reserve_seconds, None)
        assert isinstance(report, FullReport)
        # Exclude execution metadata
        raw: dict[str, Any] = {
            "schema": report.schema,
            "kind": report.kind,
            "contract": asdict(report.contract),
            "receipts": [asdict(r) for r in report.receipts],
            "inventory": list(report.inventory),
            "exclusions": list(report.exclusions),
            "findings": [asdict(f) for f in report.findings],
            "diagnostics": [asdict(d) for d in report.diagnostics],
        }
        cleaned = _clean_for_canonical(raw)
        encoded = encode_record(cleaned, limits)
        if deadline.is_work_exhausted():
            raise LimitExceeded("deadline_exceeded", "work_cutoff", deadline.duration_seconds - deadline.reserve_seconds, None)
        return encoded

    elif report.kind == "limit_failure":
        if deadline.is_final_exhausted():
            raise LimitExceeded("deadline_exceeded", "final_cutoff", deadline.duration_seconds, None)
        assert isinstance(report, LimitFailure)
        raw = {
            "schema": report.schema,
            "kind": report.kind,
            "known_inputs": report.known_inputs,
            "exit_code": report.exit_code,
            "analysis_complete": report.analysis_complete,
            "details_omitted": report.details_omitted,
            "cause": report.cause,
            "limit": report.limit,
            "omitted_domains": list(report.omitted_domains),
        }
        cleaned = _clean_for_canonical(raw)
        encoded = encode_record(cleaned, limits)
        if len(encoded) > 16384:
            raise ValueError(f"LimitFailure payload size ({len(encoded)}) exceeds 16,384 bytes reserve cap")
        return encoded
    else:
        raise ValueError(f"Unknown report kind: {report}")
