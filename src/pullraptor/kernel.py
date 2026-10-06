"""PullRaptor review orchestration kernel."""

from __future__ import annotations

from dataclasses import asdict
import json

import hashlib
import os
from pathlib import Path
import sys
import time
from typing import Any

from pullraptor.cache import cache_key, load_facts, store_facts
from pullraptor.config import load_config, matches_path
from pullraptor.diff import changes
from pullraptor.evidence import align_findings, decide, validate_receipts
from pullraptor.git_snapshot import read_blob, read_snapshot, resolve_inputs
from pullraptor.models import (
    BoundFacts,
    CoverageReceipt,
    Deadline,
    Diagnostic,
    Finding,
    FullReport,
    LimitFailure,
    LimitExceeded,
    Limits,
    RecordLimits,
    Report,
    ReviewContract,
    ScopeEntry,
    Snapshot,
    file_scope_key,
    import_scope_key,
)
from pullraptor.language_workers import LanguageRegistry
from pullraptor.parser_worker import EXTRACTOR_DIGEST
from pullraptor.python_facts import bind_facts, extract_python, resolve_context
from pullraptor.python_ir import BoundStatementIR
from pullraptor.rules import evaluate_rules
from pullraptor.security_flow import FlowResult, analyze_bound_ir, pysec001_model


def analyze_python_security_flow(
    bound: BoundStatementIR,
    *,
    limits: Limits,
    deadline: Deadline,
) -> FlowResult:
    """Advisory PYSEC001 hazard analysis over bound statement IR (not merged into findings yet)."""
    return analyze_bound_ir(bound, pysec001_model(), limits=limits, deadline=deadline)


def review(
    repo: Path,
    base_ref: str,
    head_ref: str,
    overrides: dict[str, Any] | None = None,
    *,
    started_at: float | None = None,
    ci: bool = False,
    exact_base: bool = False,
    use_cache: bool = True,
    is_head_tree: bool = False,
    language_registry: LanguageRegistry | None = None,
) -> tuple[Report, Deadline, RecordLimits]:
    """Execute a complete, immutable review comparing base and head revisions.

    Returns the canonical Report, active Deadline, and RecordLimits.
    """
    start_time = started_at if started_at is not None else time.monotonic()
    initial_deadline = Deadline(started_at=start_time, duration_seconds=3.0, reserve_seconds=2.0)
    record_limits = RecordLimits()

    base_tip = comparison_base = head = None
    policy_digest = None
    try:
        # 1. Resolve immutable Git commits
        base_tip, comparison_base, head = resolve_inputs(
            repo, base_ref, head_ref, Limits(), initial_deadline, exact_base=exact_base, is_head_tree=is_head_tree
        )

        # 2. Read base-tip snapshot to discover trusted policy (.pullraptor.toml)
        base_tip_snap = read_snapshot(repo, base_tip, Limits(), initial_deadline)
        policy_blob = next((b for b in base_tip_snap.blobs if b.path == ".pullraptor.toml"), None)
        if policy_blob is not None:
            policy_bytes = read_blob(repo, policy_blob.blob_oid, Limits(), initial_deadline)
            policy_digest = hashlib.sha256(policy_bytes).hexdigest()
        else:
            policy_bytes = None
            policy_digest = "default_policy"

    except (RuntimeError, TimeoutError, ValueError):
        if not initial_deadline.is_work_exhausted():
            raise
        return (LimitFailure("1", "limit_failure", {"base_tip": base_tip, "comparison_base": comparison_base,
                "head": head, "policy_digest": policy_digest, "reviewer_digest": None}, 2, False, True,
                "deadline_exceeded", {"name": "bootstrap_work_seconds", "cap": 1, "observed": 1},
                ({"domain": "scope", "count": None},)), initial_deadline, record_limits)

    # 3. Load trusted declarative configuration
    config = load_config(policy_bytes, overrides, ci=ci)
    record_limits = RecordLimits(max_depth=config.max_report_depth, max_aggregate_items=config.max_report_items,
                                 max_string_bytes=config.max_report_string_bytes, max_payload_bytes=config.max_report_bytes)
    semantic_config = {key: value for key, value in asdict(config).items()
                       if key not in {"use_cache", "cache_dir", "max_cache_bytes"}}
    config_digest = hashlib.sha256(json.dumps(semantic_config, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    tool_digest = f"pullraptor_v1_py{sys.version_info.major}.{sys.version_info.minor}"

    effective_limits = Limits(
        parse_timeout_seconds=config.parse_timeout_seconds,
        review_timeout_seconds=config.review_timeout_seconds,
        failure_reserve_seconds=config.failure_reserve_seconds,
        max_tracked_entries=config.max_tracked_entries,
        max_blob_bytes=config.max_blob_bytes,
        max_total_bytes=config.max_total_bytes,
        max_cache_bytes=config.max_cache_bytes,
    )
    deadline = Deadline(
        started_at=start_time,
        duration_seconds=config.review_timeout_seconds,
        reserve_seconds=config.failure_reserve_seconds,
    )

    # Cache directory configuration: CI strictly disables caching
    if ci or not use_cache or not config.use_cache:
        cache_dir: Path | None = None
    else:
        cache_dir = (Path(config.cache_dir) if config.cache_dir else
                     Path.home() / ".cache" / "pullraptor" / hashlib.sha256(str(repo.resolve()).encode()).hexdigest())
        if cache_dir.resolve().is_relative_to(repo.resolve()):
            cache_dir = None

    # 4. Ingest comparison base and head snapshots
    base_snap = read_snapshot(repo, comparison_base, effective_limits, deadline)
    head_snap = read_snapshot(repo, head, effective_limits, deadline)

    # 5. Compute exact diff facts
    try:
        chgs = changes(repo, base_snap, head_snap, effective_limits, deadline)
    except LimitExceeded as error:
        return (LimitFailure("1", "limit_failure", {"base_tip": base_tip, "comparison_base": comparison_base,
                "head": head, "policy_digest": policy_digest, "reviewer_digest": tool_digest}, 2, False, True,
                error.cause, {"name": error.name, "cap": error.cap, "observed": error.observed},
                ({"domain": "scope", "count": None}, {"domain": "findings", "count": None})), deadline, record_limits)

    # Deadline check before expensive fact extraction
    if deadline.is_work_exhausted():
        limit_fail = LimitFailure(
            schema="1",
            kind="limit_failure",
            known_inputs={
                "base_tip": base_tip,
                "comparison_base": comparison_base,
                "head": head,
                "policy_digest": policy_digest,
                "reviewer_digest": tool_digest,
            },
            exit_code=2,
            analysis_complete=False,
            details_omitted=True,
            cause="deadline_exceeded",
            limit={"name": "review_timeout_seconds", "cap": config.review_timeout_seconds, "observed": time.monotonic() - start_time},
            omitted_domains=({"domain": "findings", "count": None},),
        )
        return limit_fail, deadline, record_limits

    inventory = tuple(b.path for b in head_snap.blobs if b.path)
    runtime_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    unknown_scope: list[ScopeEntry] = []
    unknown_receipts: list[CoverageReceipt] = []
    unknown_diagnostics: list[Diagnostic] = []
    for snapshot in (base_snap, head_snap):
        for blob in snapshot.blobs:
            if blob.path is not None:
                continue
            key = file_scope_key("file", snapshot.oid, blob.path_bytes, "generic_diff")
            unknown_scope.append(ScopeEntry(key, "file", snapshot.oid, "generic_diff",
                path_bytes=blob.path_bytes, reason="unsupported non-UTF-8 path"))
            unknown_receipts.append(CoverageReceipt(key, policy_digest, "generic_diff", "incomplete",
                cause="non_utf8_path", recovery="Use a UTF-8 repository path for source navigation"))
            unknown_diagnostics.append(Diagnostic("PATH_NON_UTF8", "Requested repository path cannot be represented as UTF-8.",
                cause="non_utf8_path", recovery="Use a UTF-8 repository path for source navigation"))

    # Profile: diff
    if config.profile == "diff":
        expected_scope: list[ScopeEntry] = list(unknown_scope)
        receipts: list[CoverageReceipt] = list(unknown_receipts)

        for chg in chgs:
            if chg.path:
                key = file_scope_key("file", head, chg.path_bytes, "generic_diff")
                expected_scope.append(
                    ScopeEntry(
                        key=key,
                        kind="file",
                        snapshot=head,
                        capability="generic_diff",
                        path=chg.path,
                        path_bytes=chg.path_bytes,
                        reason="changed text",
                    )
                )
                receipts.append(
                    CoverageReceipt(
                        key=key,
                        contract_digest=policy_digest,
                        capability="generic_diff",
                        status="complete",
                    )
                )

        contract = ReviewContract(
            base_tip=base_tip,
            comparison_base=comparison_base,
            head=head,
            policy_digest=policy_digest,
            config_digest=config_digest,
            tool_digest=tool_digest,
            profile="diff",
            expected_scope=tuple(expected_scope),
            discovery_complete=True,
        )
        receipt_diags = tuple(unknown_diagnostics + list(base_snap.diagnostics + head_snap.diagnostics)) + validate_receipts(contract, tuple(receipts))
        exit_code = decide(contract, tuple(receipts), (), receipt_diags, config)

        report = FullReport(
            schema="1",
            kind="full",
            contract=contract,
            receipts=tuple(receipts),
            inventory=inventory,
            exclusions=(),
            findings=(),
            diagnostics=receipt_diags,
            execution={"duration_ms": int((time.monotonic() - start_time) * 1000), "exit_code": exit_code},
        )
        return report, deadline, record_limits

    # Profile: structural
    # Extract Python facts for changed files and their in-repository static dependencies
    changed_python_paths = {
        chg.path for chg in chgs
        if chg.path and chg.path.endswith((".py", ".pyi"))
    }

    # Map paths to BlobRef
    head_blobs_by_path = {b.path: b for b in head_snap.blobs if b.path}
    base_blobs_by_path = {b.path: b for b in base_snap.blobs if b.path}

    admitted_bytes: dict[str, int] = {}
    cache_hits = cache_misses = 0

    def _extract_for_blob(blob: Any, side: str, snap: Snapshot) -> tuple[BoundFacts | None, list[Diagnostic]]:
        nonlocal cache_hits, cache_misses
        if blob.mode not in {"100644", "100755"}:
            return None, [Diagnostic("SOURCE_MODE_UNSUPPORTED", "Source is not a regular tracked blob.",
                path=blob.path, side=side, cause="unsupported_source_mode", recovery="Review the metadata exclusion or select the diff profile")]
        if blob.size > effective_limits.max_blob_bytes:
            return None, [Diagnostic("LIMIT_EXCEEDED", "Requested source exceeds the declared per-blob byte limit.",
                path=blob.path, side=side, cause="max_blob_bytes_exceeded", recovery="Increase the trusted per-blob byte limit")]
        total = admitted_bytes.get(snap.oid, 0) + blob.size
        if total > effective_limits.max_total_bytes:
            return None, [Diagnostic("LIMIT_EXCEEDED", "Requested source exceeds the declared snapshot byte limit.",
                path=blob.path, side=side, cause="max_total_bytes_exceeded", recovery="Increase the trusted snapshot byte limit")]
        admitted_bytes[snap.oid] = total
        source = read_blob(repo, blob.blob_oid, effective_limits, deadline)
        k = cache_key(hashlib.sha256(source).hexdigest(), runtime_str, "1", EXTRACTOR_DIGEST)
        cached = load_facts(cache_dir, k, effective_limits) if cache_dir else None
        if cached is not None:
            cache_hits += 1
            facts, diags = cached, []
        else:
            cache_misses += 1
            res = extract_python(source, effective_limits, deadline)
            facts, diags = res.content, list(res.diagnostics)
            if facts is not None and cache_dir:
                store_facts(cache_dir, k, facts, effective_limits)
        if facts is None:
            return None, diags
        return bind_facts(facts, source, snap, blob.path, side), diags

    expected_scope_list: list[ScopeEntry] = list(unknown_scope)
    receipts_list: list[CoverageReceipt] = list(unknown_receipts)
    head_bound_facts: list[BoundFacts] = []
    base_bound_facts: list[BoundFacts] = []
    all_diagnostics: list[Diagnostic] = list(base_snap.diagnostics + head_snap.diagnostics) + unknown_diagnostics
    discovery_complete = not all_diagnostics
    head_visited: set[str] = set()

    # Each revision discovers its own append-only static context closure. A
    # head dependency graph cannot stand in for the independently required base.
    for side, snapshot, blobs_by_path, bound_facts in (("base", base_snap, base_blobs_by_path, base_bound_facts),
                                                      ("head", head_snap, head_blobs_by_path, head_bound_facts)):
        queue = sorted(changed_python_paths)
        visited: set[str] = set()
        while queue:
            path = queue.pop(0)
            if path in visited:
                continue
            visited.add(path)
            if side == "head":
                head_visited.add(path)
            blob = blobs_by_path.get(path)
            if blob is None:
                continue
            key = file_scope_key("file", snapshot.oid, blob.path_bytes, "python_patterns")
            expected_scope_list.append(ScopeEntry(key, "file", snapshot.oid, "python_patterns",
                path=path, path_bytes=blob.path_bytes,
                reason="changed source" if path in changed_python_paths else "static dependency"))
            bound, diagnostics = _extract_for_blob(blob, side, snapshot)
            all_diagnostics.extend(diagnostics)
            if bound is None:
                discovery_complete = False
                primary = diagnostics[0] if diagnostics else None
                receipts_list.append(CoverageReceipt(key, policy_digest, "python_patterns", "incomplete",
                    cause=primary.cause if primary else "parse_failure", recovery=primary.recovery if primary else "Prepare the requested source"))
                continue
            bound_facts.append(bound)
            receipts_list.append(CoverageReceipt(key, policy_digest, "python_patterns", "complete"))
            current, _ = resolve_context((bound,), snapshot)
            queue.extend(sorted({item["target_path"] for item in current[0].resolved_imports
                                 if item.get("kind") == "repo" and item.get("target_path")} - visited))

    head_resolved, head_res_diags = resolve_context(tuple(head_bound_facts), head_snap)
    base_resolved, base_res_diags = resolve_context(tuple(base_bound_facts), base_snap)
    all_diagnostics.extend(base_res_diags + head_res_diags)

    # Lookup identity contains source/module/level, not diagnostic prose or an
    # invented path. Ambiguous and missing lookups cannot disappear from scope.
    seen_lookup_keys: set[str] = set()
    for snapshot, resolved_items in ((base_snap, base_resolved), (head_snap, head_resolved)):
        for resolved in resolved_items:
            for occurrence, lookup in zip(resolved.bound.content.imports, resolved.resolved_imports):
                if lookup.get("kind") not in {"unresolved", "ambiguous"}:
                    continue
                target = str(lookup.get("raw") or lookup.get("canonical") or "")
                level = int(occurrence.get("level", 0))
                key = import_scope_key("import_lookup", snapshot.oid, resolved.bound.path, target, level, "python_structure")
                if key in seen_lookup_keys:
                    continue
                seen_lookup_keys.add(key)
                expected_scope_list.append(ScopeEntry(key, "import_lookup", snapshot.oid, "python_structure",
                    source_occurrence=resolved.bound.path, canonical_target=target, relative_level=level,
                    reason="unresolved or ambiguous import lookup"))
                receipts_list.append(CoverageReceipt(key, policy_digest, "python_structure", "incomplete",
                    cause="unresolved_import" if lookup["kind"] == "unresolved" else "ambiguous_import",
                    recovery="Prepare or disambiguate the requested repository context"))

    # Every changed known source language remains requested on both present
    # sides. Unsupported structural capability cannot vanish from the contract.
    for change in chgs:
        if not change.path or not change.path.endswith(config.source_suffixes) or change.path.endswith((".py", ".pyi")):
            continue
        for side, snapshot, blob in (("base", base_snap, change.base_blob), ("head", head_snap, change.head_blob)):
            if blob is None:
                continue
            key = file_scope_key("file", snapshot.oid, blob.path_bytes, "python_structure")
            expected_scope_list.append(ScopeEntry(key, "file", snapshot.oid, "python_structure",
                path=change.path, path_bytes=blob.path_bytes, reason="changed unsupported source"))
            receipts_list.append(CoverageReceipt(key, policy_digest, "python_structure", "incomplete",
                cause="unsupported_language", recovery="Select the explicit diff profile or an independently admitted language worker"))
            all_diagnostics.append(Diagnostic("UNSUPPORTED_LANGUAGE", "Requested structural analysis is unavailable for this source language.",
                path=change.path, side=side, cause="unsupported_language",
                recovery="Select the explicit diff profile or an independently admitted language worker"))

    # 6. Evaluate rules
    base_findings = evaluate_rules(base_resolved, base_snap, config)
    head_findings = evaluate_rules(head_resolved, head_snap, config)

    # 7. Align findings
    comparable = (len(base_res_diags) == 0 and all(r.status == "complete" for r in receipts_list))
    aligned_findings = align_findings(base_findings, head_findings, comparable=comparable)

    # 8. Seal contract and validate receipts
    contract = ReviewContract(
        base_tip=base_tip,
        comparison_base=comparison_base,
        head=head,
        policy_digest=policy_digest,
        config_digest=config_digest,
        tool_digest=tool_digest,
        profile="structural",
        expected_scope=tuple(sorted(expected_scope_list, key=lambda item: item.key)),
        discovery_complete=discovery_complete,
    )
    receipt_diags = validate_receipts(contract, tuple(receipts_list))
    all_diagnostics.extend(receipt_diags)

    # 9. Policy decision
    exit_code = decide(contract, tuple(receipts_list), aligned_findings, tuple(all_diagnostics), config)

    execution: dict[str, Any] = {
        "duration_ms": int((time.monotonic() - start_time) * 1000),
        "exit_code": exit_code,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_enabled": cache_dir is not None,
    }
    if config.profile == "structural":
        from pullraptor.review_execution import (
            collect_advisory_security_observations,
            dispatch_language_workers_for_changes,
        )

        changed_paths = tuple(
            chg.path for chg in chgs if chg.path and chg.path in head_visited
        )
        advisories = collect_advisory_security_observations(
            repo,
            changed_paths,
            head_blobs_by_path,
            head,
            policy_digest,
            effective_limits,
            deadline,
        )
        if advisories:
            execution["advisory_observations"] = advisories
        if language_registry is not None:
            worker_records = dispatch_language_workers_for_changes(
                repo,
                tuple(chg.path for chg in chgs if chg.path),
                head_blobs_by_path,
                head,
                policy_digest,
                language_registry,
                effective_limits,
                deadline,
            )
            if worker_records:
                execution["language_workers"] = worker_records

    report = FullReport(
        schema="1",
        kind="full",
        contract=contract,
        receipts=tuple(receipts_list),
        inventory=inventory,
        exclusions=(),
        findings=aligned_findings,
        diagnostics=tuple(all_diagnostics),
        execution=execution,
    )
    return report, deadline, record_limits
