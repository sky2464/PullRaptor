"""PullRaptor review orchestration kernel."""

from __future__ import annotations

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
    Limits,
    RecordLimits,
    Report,
    ReviewContract,
    ScopeEntry,
    Snapshot,
    file_scope_key,
    import_scope_key,
)
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
) -> tuple[Report, Deadline, RecordLimits]:
    """Execute a complete, immutable review comparing base and head revisions.

    Returns the canonical Report, active Deadline, and RecordLimits.
    """
    start_time = started_at if started_at is not None else time.monotonic()
    initial_deadline = Deadline(started_at=start_time, duration_seconds=60.0, reserve_seconds=2.0)
    record_limits = RecordLimits()

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

    # 3. Load trusted declarative configuration
    config = load_config(policy_bytes, overrides, ci=ci)
    config_digest = hashlib.sha256(str(config).encode("utf-8")).hexdigest()
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
        cache_dir = Path(config.cache_dir) if config.cache_dir else (repo / ".pullraptor_cache")

    # 4. Ingest comparison base and head snapshots
    base_snap = read_snapshot(repo, comparison_base, effective_limits, deadline)
    head_snap = read_snapshot(repo, head, effective_limits, deadline)

    # 5. Compute exact diff facts
    chgs = changes(repo, base_snap, head_snap, effective_limits, deadline)

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

    # Profile: diff
    if config.profile == "diff":
        expected_scope: list[ScopeEntry] = []
        receipts: list[CoverageReceipt] = []

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
        receipt_diags = validate_receipts(contract, tuple(receipts))
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
        if chg.path and chg.path.endswith(".py")
    }

    # Map paths to BlobRef
    head_blobs_by_path = {b.path: b for b in head_snap.blobs if b.path}
    base_blobs_by_path = {b.path: b for b in base_snap.blobs if b.path}

    def _extract_for_blob(blob: Any, side: str, snap: Snapshot) -> tuple[BoundFacts | None, list[Diagnostic]]:
        source = read_blob(repo, blob.blob_oid, effective_limits, deadline)
        k = cache_key(blob.blob_oid, runtime_str, "1", EXTRACTOR_DIGEST)
        cached = load_facts(cache_dir, k, effective_limits) if cache_dir else None

        if cached is not None:
            facts = cached
            diags: list[Diagnostic] = []
        else:
            res = extract_python(source, effective_limits, deadline)
            facts = res.content
            diags = list(res.diagnostics)
            if facts is not None and cache_dir:
                store_facts(cache_dir, k, facts, effective_limits)

        if facts is None:
            return None, diags

        bound = bind_facts(facts, source, snap, blob.path, side)
        return bound, diags

    expected_scope_list: list[ScopeEntry] = []
    receipts_list: list[CoverageReceipt] = []
    head_bound_facts: list[BoundFacts] = []
    base_bound_facts: list[BoundFacts] = []
    all_diagnostics: list[Diagnostic] = []

    # Queue of files to analyze in head
    head_queue = list(changed_python_paths)
    head_visited: set[str] = set()

    while head_queue:
        curr_path = head_queue.pop(0)
        if curr_path in head_visited:
            continue
        head_visited.add(curr_path)

        blob = head_blobs_by_path.get(curr_path)
        if not blob:
            continue

        scope_key = file_scope_key("file", head, blob.path_bytes, "python_patterns")
        expected_scope_list.append(
            ScopeEntry(
                key=scope_key,
                kind="file",
                snapshot=head,
                capability="python_patterns",
                path=curr_path,
                path_bytes=blob.path_bytes,
                reason="changed source" if curr_path in changed_python_paths else "static dependency",
            )
        )

        bound, diags = _extract_for_blob(blob, "head", head_snap)
        all_diagnostics.extend(diags)

        if bound is not None:
            head_bound_facts.append(bound)
            receipts_list.append(
                CoverageReceipt(
                    key=scope_key,
                    contract_digest=policy_digest,
                    capability="python_patterns",
                    status="complete",
                )
            )

            # Discover static repo dependencies
            for imp in bound.content.imports:
                mod = imp.get("module") or imp.get("name") or ""
                candidate_path = f"{mod.replace('.', '/')}.py"
                candidate_init = f"{mod.replace('.', '/')}/__init__.py"
                candidate_src_path = f"src/{candidate_path}"
                candidate_src_init = f"src/{candidate_init}"

                if candidate_path in head_blobs_by_path:
                    head_queue.append(candidate_path)
                elif candidate_init in head_blobs_by_path:
                    head_queue.append(candidate_init)
                elif candidate_src_path in head_blobs_by_path:
                    head_queue.append(candidate_src_path)
                elif candidate_src_init in head_blobs_by_path:
                    head_queue.append(candidate_src_init)
        else:
            receipts_list.append(
                CoverageReceipt(
                    key=scope_key,
                    contract_digest=policy_digest,
                    capability="python_patterns",
                    status="incomplete",
                    cause="parse_failure",
                    recovery="Fix Python syntax error",
                )
            )

    # Also analyze matching baseline files for differential alignment
    for path in head_visited:
        base_blob = base_blobs_by_path.get(path)
        if base_blob:
            bound_b, diags_b = _extract_for_blob(base_blob, "base", base_snap)
            all_diagnostics.extend(diags_b)
            if bound_b is not None:
                base_bound_facts.append(bound_b)

    # Contextual resolution
    head_resolved, head_res_diags = resolve_context(tuple(head_bound_facts), head_snap)
    base_resolved, base_res_diags = resolve_context(tuple(base_bound_facts), base_snap)
    all_diagnostics.extend(head_res_diags)
    all_diagnostics.extend(base_res_diags)

    # Unresolved imports produce distinct scope entries and incomplete receipts
    seen_imp_keys: set[str] = set()
    for d in head_res_diags:
        if d.code == "IMPORT_UNRESOLVED" and d.path:
            imp_key = import_scope_key(
                kind="import_lookup",
                snapshot=head,
                source_occurrence=d.path,
                canonical_target=d.message,
                relative_level=0,
                capability="python_structure",
            )
            if imp_key in seen_imp_keys:
                continue
            seen_imp_keys.add(imp_key)
            expected_scope_list.append(
                ScopeEntry(
                    key=imp_key,
                    kind="import_lookup",
                    snapshot=head,
                    capability="python_structure",
                    source_occurrence=d.path,
                    canonical_target=d.message,
                    relative_level=0,
                    reason="unresolved import lookup",
                )
            )
            receipts_list.append(
                CoverageReceipt(
                    key=imp_key,
                    contract_digest=policy_digest,
                    capability="python_structure",
                    status="incomplete",
                    cause="unresolved_import",
                    recovery="Provide repository candidate or configure modeled external",
                )
            )

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
        expected_scope=tuple(expected_scope_list),
        discovery_complete=True,
    )
    receipt_diags = validate_receipts(contract, tuple(receipts_list))
    all_diagnostics.extend(receipt_diags)

    # 9. Policy decision
    exit_code = decide(contract, tuple(receipts_list), aligned_findings, tuple(all_diagnostics), config)

    report = FullReport(
        schema="1",
        kind="full",
        contract=contract,
        receipts=tuple(receipts_list),
        inventory=inventory,
        exclusions=(),
        findings=aligned_findings,
        diagnostics=tuple(all_diagnostics),
        execution={"duration_ms": int((time.monotonic() - start_time) * 1000), "exit_code": exit_code},
    )
    return report, deadline, record_limits
