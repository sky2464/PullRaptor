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
                    code="DEADLINE_EXCEEDED",
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
    # Build repository module inventory from manifest
    repo_modules: dict[str, str] = {}
    for blob in manifest.blobs:
        if blob.path and blob.path.endswith(".py"):
            parts = blob.path[:-3].split("/")
            if parts[-1] == "__init__":
                mod_name = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]
            else:
                mod_name = ".".join(parts)
            repo_modules[mod_name] = blob.path

            if parts[0] == "src" and len(parts) > 1:
                src_parts = parts[1:]
                if src_parts[-1] == "__init__":
                    src_mod_name = ".".join(src_parts[:-1]) if len(src_parts) > 1 else src_parts[0]
                else:
                    src_mod_name = ".".join(src_parts)
                repo_modules[src_mod_name] = blob.path

    stdlib_modules = getattr(sys, "stdlib_module_names", set())

    resolved_list: list[ResolvedFacts] = []
    diagnostics: list[Diagnostic] = []

    for bound in facts:
        resolved_imports: list[dict[str, Any]] = []

        for imp in bound.content.imports:
            mod = imp.get("module") or imp.get("name") or ""
            # Canonical module target (top-level package or module)
            canonical = mod.split(".")[0] if mod else ""

            # 1. Repository candidate takes priority (shadows stdlib/external)
            if mod in repo_modules:
                resolved_imports.append({
                    "raw": mod,
                    "canonical": canonical,
                    "kind": "repo",
                    "target_path": repo_modules[mod],
                })
            elif canonical in repo_modules:
                resolved_imports.append({
                    "raw": mod,
                    "canonical": canonical,
                    "kind": "repo",
                    "target_path": repo_modules[canonical],
                })
            elif any(k == canonical or k.startswith(canonical + ".") for k in repo_modules):
                matching_path = next(v for k, v in repo_modules.items() if k == canonical or k.startswith(canonical + "."))
                resolved_imports.append({
                    "raw": mod,
                    "canonical": canonical,
                    "kind": "repo",
                    "target_path": matching_path,
                })
            # 2. Pinned standard library
            elif canonical in stdlib_modules:
                resolved_imports.append({
                    "raw": mod,
                    "canonical": canonical,
                    "kind": "stdlib",
                    "target_path": None,
                })
            # 3. Unresolved external
            else:
                resolved_imports.append({
                    "raw": mod,
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
                        recovery=f"Add {canonical}.py to repository or configure modeled external",
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
