"""PullRaptor Python fact extraction, occurrence binding, and contextual resolution."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
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
)
from pullraptor.parser_worker import parse_and_extract


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

    res = parse_and_extract(source)
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

    raw_content = res["content"]
    content_facts = ContentFacts(
        blob_digest=raw_content["blob_digest"],
        runtime_version=raw_content["runtime_version"],
        schema_version=raw_content["schema_version"],
        extractor_digest=raw_content["extractor_digest"],
        symbols=tuple(raw_content["symbols"]),
        imports=tuple(raw_content["imports"]),
        pattern_facts=tuple(raw_content["pattern_facts"]),
        unsupported_constructs=tuple(raw_content["unsupported_constructs"]),
        relative_locations=tuple(raw_content["relative_locations"]),
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
