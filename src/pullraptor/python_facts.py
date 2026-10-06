"""PullRaptor Python fact extraction, occurrence binding, and contextual resolution."""

from __future__ import annotations

import hashlib
import base64
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from pullraptor.models import (
    BoundFacts,
    ContentFacts,
    Deadline,
    Diagnostic,
    FactResult,
    Limits,
    ResolvedFacts,
    Snapshot,
    Span,
    ProcessBounds,
    decode_record,
)
from pullraptor.parser_worker import EXTRACTOR_DIGEST
from pullraptor.process import run_bounded


def content_record(raw: dict[str, Any]) -> ContentFacts:
    """Strict occurrence-free fact boundary shared by worker and private cache."""
    required = {"blob_digest", "runtime_version", "schema_version", "extractor_digest", "symbols", "imports", "pattern_facts", "unsupported_constructs", "relative_locations"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("invalid fact fields")
    for field in ("blob_digest", "extractor_digest"):
        if not isinstance(raw[field], str) or not re.fullmatch(r"[0-9a-f]{64}", raw[field]):
            raise ValueError("invalid fact identity")
    if raw["schema_version"] != "1" or not isinstance(raw["runtime_version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", raw["runtime_version"]):
        raise ValueError("invalid fact version")
    for field in ("symbols", "imports", "pattern_facts", "unsupported_constructs", "relative_locations"):
        if not isinstance(raw[field], list):
            raise ValueError("invalid fact collection")
    if raw["relative_locations"] or any(not isinstance(item, str) for item in raw["unsupported_constructs"]):
        raise ValueError("unsupported relative location record")
    coordinate_keys = {"start_line", "end_line", "start_byte", "end_byte", "start_column", "end_column"}
    for field in ("symbols", "imports", "pattern_facts"):
        for fact in raw[field]:
            if not isinstance(fact, dict) or not isinstance(fact.get("coords"), dict):
                raise ValueError("invalid fact record")
            coords = fact["coords"]
            if set(coords) != coordinate_keys or any(type(v) is not int for v in coords.values()):
                raise ValueError("invalid coordinates")
            Span("fact", "head", **coords)
            if field == "symbols":
                if set(fact) != {"kind", "name", "coords"} or fact["kind"] != "function" or not isinstance(fact["name"], str):
                    raise ValueError("invalid symbol")
            elif field == "imports":
                keys = {"kind", "module", "asname", "level", "coords"} | ({"name"} if fact.get("kind") == "import_from" else set())
                if set(fact) != keys or fact["kind"] not in ("import", "import_from") or type(fact["level"]) is not int or fact["level"] < 0 or any(not isinstance(fact[k], str) for k in keys - {"level", "coords"}):
                    raise ValueError("invalid import")
            else:
                keys = {"rule", "version", "coords", "witness"} | ({"param", "type"} if fact.get("rule") == "PY001" else {"call"} if fact.get("rule") == "PY003" else set())
                if set(fact) != keys or fact["rule"] not in ("PY001", "PY002", "PY003") or fact["version"] != "1.0" or any(not isinstance(fact[k], str) for k in keys - {"coords"}):
                    raise ValueError("invalid pattern")
    return ContentFacts(**{**raw, **{key: tuple(raw[key]) for key in ("symbols", "imports", "pattern_facts", "unsupported_constructs", "relative_locations")}})


def extract_python(
    source: bytes,
    limits: Limits,
    deadline: Deadline,
) -> FactResult:
    """Extract occurrence-free syntactic facts from Python source.

    Enforces blob size bounds and deadlines.
    """
    if len(source) > limits.max_blob_bytes:
        return FactResult(
            content=None,
            diagnostics=(
                Diagnostic(
                    code="LIMIT_EXCEEDED",
                    message=f"Source blob size ({len(source)}) exceeds max_blob_bytes ({limits.max_blob_bytes})",
                    cause="max_blob_bytes_exceeded",
                    recovery="Increase max_blob_bytes in policy or omit file",
                ),
            ),
        )

    if deadline.is_work_exhausted():
        return FactResult(
            content=None,
            diagnostics=(
                Diagnostic(
                    code="TIMEOUT",
                    message="Parse deadline exhausted before extraction",
                    cause="deadline_exhausted",
                ),
            ),
        )

    request = json.dumps({"protocol": "pullraptor_worker_v1", "source_base64": base64.b64encode(source).decode("ascii")}, separators=(",", ":")).encode()
    with tempfile.TemporaryDirectory(prefix="pullraptor-parser-") as neutral:
        result = run_bounded((sys.executable, "-I", "-S", str(Path(__file__).with_name("parser_worker.py").resolve())),
            cwd=Path(neutral), env={}, deadline=deadline,
            bounds=ProcessBounds(limits.record_limits.max_payload_bytes, limits.max_stderr_bytes, limits.parse_timeout_seconds),
            input_bytes=request, max_input_bytes=min(4_194_304, 4 * ((limits.max_blob_bytes + 2) // 3) + 128))
    if result.returncode or result.timed_out or result.stdout_truncated or result.stderr_truncated:
        code = "TIMEOUT" if result.timed_out else "LIMIT_EXCEEDED" if result.stdout_truncated or result.stderr_truncated else "PY_PARSE_FAILED"
        return FactResult(None, (Diagnostic(code, "Isolated Python extraction did not complete within its trusted bounds.", cause="worker_failure", recovery="Reduce source complexity or retry with an approved limit."),))
    try:
        res = decode_record(result.stdout, schema="worker", limits=limits.record_limits)
        if res.get("protocol") != "pullraptor_worker_v1" or type(res.get("success")) is not bool or set(res) != ({"protocol", "success", "content"} if res["success"] else {"protocol", "success", "error"}):
            raise ValueError("invalid worker response")
        if res["success"]:
            content_facts = content_record(res["content"])
            if content_facts.blob_digest != hashlib.sha256(source).hexdigest() or content_facts.extractor_digest != EXTRACTOR_DIGEST or content_facts.runtime_version != f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}":
                raise ValueError("stale worker response")
        else:
            err = res["error"]
            if not isinstance(err, dict) or set(err) != {"code", "message", "line", "column"} or err["code"] != "PY_PARSE_FAILED" or not isinstance(err["message"], str) or type(err["line"]) is not int or type(err["column"]) is not int:
                raise ValueError("invalid worker error")
    except (ValueError, KeyError, TypeError):
        return FactResult(None, (Diagnostic("PY_PARSE_FAILED", "Invalid or stale isolated parser record; semantic review skipped.", cause="invalid_worker_record"),))
    if not res.get("success"):
        err = res.get("error", {})
        return FactResult(
            content=None,
            diagnostics=(
                Diagnostic(
                    code=err.get("code", "PY_PARSE_FAILED"),
                    message=err.get("message", "Python parse failed"),
                    cause="syntax_error",
                    recovery="Fix Python syntax error",
                ),
            ),
        )

    return FactResult(content=content_facts, diagnostics=())


def bind_facts(
    content: ContentFacts,
    source: bytes,
    snapshot: Snapshot,
    path: str,
    side: str,
) -> BoundFacts:
    """Bind occurrence-free syntactic facts to a validated snapshot occurrence.

    Verifies blob digest against current source bytes.
    """
    actual_digest = hashlib.sha256(source).hexdigest()
    if actual_digest != content.blob_digest:
        raise ValueError(
            f"Blob digest mismatch during binding: expected {content.blob_digest}, got {actual_digest}"
        )

    if side not in ("base", "head"):
        raise ValueError(f"side must be 'base' or 'head', got {side!r}")

    # Check path presence in snapshot
    found = any(b.path == path for b in snapshot.blobs)
    if not found:
        raise ValueError(f"Path {path!r} not found in snapshot {snapshot.oid}")
    lines = source.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    for record in (*content.symbols, *content.imports, *content.pattern_facts):
        coords = record["coords"]
        Span(path, side, **coords)
        for end in ("start", "end"):
            line, byte, column = (coords[f"{end}_{suffix}"] for suffix in ("line", "byte", "column"))
            if line > len(lines) or byte > len(source) or not starts[line - 1] <= byte <= starts[line]:
                raise ValueError("Fact coordinate is outside bound source")
            prefix = source[starts[line - 1]:byte]
            if len(prefix.decode("utf-8", errors="strict")) + 1 != column:
                raise ValueError("Fact byte and character locations disagree")

    return BoundFacts(
        content=content,
        snapshot=snapshot.oid,
        path=path,
        side=side,
    )


def resolve_context(
    facts: tuple[BoundFacts, ...],
    manifest: Snapshot,
) -> tuple[tuple[ResolvedFacts, ...], tuple[Diagnostic, ...]]:
    """Conservatively resolve imports and symbols against current full manifest and stdlib."""
    py_blobs = [b.path for b in manifest.blobs if b.path and b.path.endswith(".py")]
    stdlib_modules = getattr(sys, "stdlib_module_names", set())

    resolved_list: list[ResolvedFacts] = []
    diagnostics: list[Diagnostic] = []

    for bound in facts:
        bound_dir = Path(bound.path).parent
        resolved_imports: list[dict[str, Any]] = []

        for imp in bound.content.imports:
            raw_mod = imp.get("canonical") or imp.get("module") or imp.get("name") or ""
            canonical = raw_mod.split(".")[0] if raw_mod else ""
            level = imp.get("level", 0)

            parts = canonical.split(".")
            file_cand = "/".join(parts) + ".py"
            pkg_cand = "/".join(parts) + "/__init__.py"

            matches: list[str] = []
            if level > 0:
                rel_base = bound_dir
                for _ in range(level - 1):
                    rel_base = rel_base.parent
                rel_file = (rel_base / file_cand).as_posix()
                rel_pkg = (rel_base / pkg_cand).as_posix()
                matches = [p for p in py_blobs if p in (rel_file, rel_pkg)]
            else:
                matches = [
                    p for p in py_blobs
                    if p in (file_cand, pkg_cand) or p.endswith("/" + file_cand) or p.endswith("/" + pkg_cand)
                ]

            if len(matches) > 1:
                resolved_imports.append({
                    "raw": raw_mod,
                    "canonical": canonical,
                    "kind": "ambiguous",
                    "target_path": None,
                })
                diagnostics.append(
                    Diagnostic(
                        code="IMPORT_AMBIGUOUS",
                        message=f"PullRaptor: IMPORT_AMBIGUOUS in {bound.path}: multiple candidates {matches} for '{canonical}'",
                        path=bound.path,
                        side=bound.side,
                        cause="ambiguous_candidates",
                        recovery="Use explicit package path or disambiguate module names",
                    )
                )
            elif len(matches) == 1:
                resolved_imports.append({
                    "raw": raw_mod,
                    "canonical": canonical,
                    "kind": "repo",
                    "target_path": matches[0],
                })
            elif canonical in stdlib_modules:
                resolved_imports.append({
                    "raw": raw_mod,
                    "canonical": canonical,
                    "kind": "stdlib",
                    "target_path": None,
                })
            else:
                resolved_imports.append({
                    "raw": raw_mod,
                    "canonical": canonical,
                    "kind": "unresolved",
                    "target_path": None,
                })
                diagnostics.append(
                    Diagnostic(
                        code="IMPORT_UNRESOLVED",
                        message=f"PullRaptor: IMPORT_UNRESOLVED in {bound.path}: external module '{canonical}' could not be resolved in repository",
                        path=bound.path,
                        side=bound.side,
                        cause="missing_dependency",
                        recovery=f"Add {canonical}.py to repository or declare external package model",
                    )
                )

        resolved_list.append(
            ResolvedFacts(
                bound=bound,
                resolved_imports=tuple(resolved_imports),
                resolved_symbols=(),
            )
        )

    return tuple(resolved_list), tuple(diagnostics)
