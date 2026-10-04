"""Post-kernel review execution wiring (E03/E04/E05 entry orchestration)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import time
from typing import Any
from urllib.parse import urlparse

from pullraptor.ai_adapter import (
    AIConfig,
    ExternalContext,
    build_explanation_prompt,
    request_ai_proposals,
    request_ai_proposals_via_transport,
)
from pullraptor.ai_context import ContextBlock, ContextManifest, block_digest, select_context
from pullraptor.ai_transport import AIBudget, ProviderPolicy
from pullraptor.conversation import Conversation, answer, deterministic_explanation, invoke_for_conversation
from pullraptor.git_snapshot import read_blob
from pullraptor.kernel import analyze_python_security_flow, review
from pullraptor.language_workers import (
    LanguageRegistry,
    LanguageRegistryEntry,
    LanguageRequest,
    LanguageResult,
    digest_executable_script,
    run_language,
)
from pullraptor.models import Deadline, FullReport, Limits, RecordLimits, Report, canonical_bytes
from pullraptor.python_ir import bind_statement_ir
from pullraptor.python_lowering import lower_python_source
from pullraptor.security_flow import SecurityObservation


@dataclass(frozen=True)
class ReviewExecutionOptions:
    """Optional enrichment applied after deterministic kernel review."""

    ai_config: AIConfig | None = None
    external_context: ExternalContext | None = None
    ai_permitted_addresses: tuple[str, ...] = ()
    conversation_question: str = ""
    use_ai_transport: bool = True

    @classmethod
    def from_cli(
        cls,
        *,
        ai_endpoint: str | None,
        ai_model: str,
        ai_token: str | None,
        context_issue: str = "",
        context_ci_log: str = "",
        conversation_question: str = "",
        permitted_addresses: str | None = None,
    ) -> ReviewExecutionOptions:
        ai_cfg: AIConfig | None = None
        if ai_endpoint:
            addrs = tuple(a.strip() for a in (permitted_addresses or "").split(",") if a.strip())
            ai_cfg = AIConfig(
                enabled=True,
                endpoint=ai_endpoint,
                model=ai_model,
                api_key=ai_token or "",
            )
            return cls(
                ai_config=ai_cfg,
                external_context=ExternalContext(
                    issue_text=context_issue,
                    ci_log_snippet=context_ci_log,
                ),
                ai_permitted_addresses=addrs,
                conversation_question=conversation_question or "",
            )
        return cls(
            external_context=ExternalContext(issue_text=context_issue, ci_log_snippet=context_ci_log),
            conversation_question=conversation_question or "",
            use_ai_transport=False,
        )


def load_language_registry_json(path: Path) -> LanguageRegistry:
    """Load a trusted language worker registry from JSON (operator-owned policy)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries_raw = raw.get("entries", ())
    if not isinstance(entries_raw, list):
        raise ValueError("registry entries must be a list")
    entries: list[LanguageRegistryEntry] = []
    for item in entries_raw:
        if not isinstance(item, dict):
            raise ValueError("registry entry must be an object")
        argv = tuple(str(x) for x in item.get("executable_argv", ()))
        entry = LanguageRegistryEntry(
            language=str(item["language"]),
            capability=str(item["capability"]),
            executable_argv=argv,
            executable_digest=str(item.get("executable_digest") or digest_executable_script(argv)),
            grammar_digest=str(item["grammar_digest"]),
            allowed_environment=tuple(
                (str(k), str(v)) for k, v in item.get("allowed_environment", [])
            ),
            worker_cwd=str(item.get("worker_cwd", ".")),
        )
        entries.append(entry)
    return LanguageRegistry(entries=tuple(entries))


def run_review(
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
    execution_options: ReviewExecutionOptions | None = None,
) -> tuple[Report, Deadline, RecordLimits]:
    """Run kernel review plus optional post-kernel enrichment."""
    report, deadline, record_limits = review(
        repo,
        base_ref,
        head_ref,
        overrides,
        started_at=started_at,
        ci=ci,
        exact_base=exact_base,
        use_cache=use_cache,
        is_head_tree=is_head_tree,
        language_registry=language_registry,
    )
    if execution_options is not None:
        apply_post_kernel_enrichment(report, deadline, record_limits, execution_options)
    return report, deadline, record_limits


def apply_post_kernel_enrichment(
    report: Report,
    deadline: Deadline,
    record_limits: RecordLimits,
    options: ReviewExecutionOptions,
) -> None:
    """Attach untrusted AI proposals and conversation answers to report.execution."""
    if report.kind != "full":
        return
    assert isinstance(report, FullReport)

    digest = hashlib.sha256(canonical_bytes(report, limits=record_limits, deadline=deadline)).hexdigest()
    manifest = _context_manifest(report, digest, options.external_context or ExternalContext())

    if options.ai_config and options.ai_config.enabled and report.findings:
        _attach_ai_proposals(report, deadline, record_limits, options, manifest)

    if options.conversation_question:
        _attach_conversation_answer(report, deadline, record_limits, options, digest, manifest)


def _context_manifest(
    report: FullReport,
    report_digest: str,
    context: ExternalContext,
) -> ContextManifest:
    blocks: list[ContextBlock] = []
    if context.issue_text.strip():
        payload = context.issue_text.strip().encode("utf-8")
        blocks.append(
            ContextBlock(
                id="issue",
                kind="issue",
                producer="cli",
                source_revision=report_digest,
                digest=block_digest(payload),
                serialized_bytes=payload,
                mandatory=False,
                priority=1,
            )
        )
    if context.ci_log_snippet.strip():
        payload = context.ci_log_snippet.strip().encode("utf-8")
        blocks.append(
            ContextBlock(
                id="ci_log",
                kind="ci_log",
                producer="cli",
                source_revision=report_digest,
                digest=block_digest(payload),
                serialized_bytes=payload,
                mandatory=False,
                priority=2,
            )
        )
    if report.findings:
        summary = build_explanation_prompt(report.findings, context, max_bytes=16_384)
        payload = summary.encode("utf-8")
        blocks.append(
            ContextBlock(
                id="findings",
                kind="findings_summary",
                producer="kernel",
                source_revision=report_digest,
                digest=block_digest(payload),
                serialized_bytes=payload,
                mandatory=True,
                priority=0,
            )
        )
    return ContextManifest(
        report_digest=report_digest,
        head=report.contract.head,
        blocks=tuple(blocks),
        retrieval_receipts=(json.dumps({"head": report.contract.head}),),
    )


def _provider_policy(config: AIConfig, permitted: tuple[str, ...]) -> ProviderPolicy:
    parsed = urlparse(config.endpoint)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    return ProviderPolicy(
        profile="cli",
        approved_origin=origin,
        approved_path=path,
        permitted_addresses=permitted,
        credential_reference="bearer" if config.api_key else "",
        spend_cap=None,
        retention_policy="operator_defined",
    )


def _attach_ai_proposals(
    report: FullReport,
    deadline: Deadline,
    record_limits: RecordLimits,
    options: ReviewExecutionOptions,
    manifest: ContextManifest,
) -> None:
    cfg = options.ai_config
    if cfg is None or not cfg.enabled:
        return
    ctx = options.external_context or ExternalContext()
    proposals: tuple[Any, ...] = ()
    transport_state: str | None = None

    if options.use_ai_transport and cfg.endpoint.startswith("https://"):
        selection = select_context(manifest, cfg.max_context_bytes)
        budget = AIBudget(
            max_requests=cfg.max_requests,
            context_bytes=cfg.max_context_bytes,
            output_tokens=cfg.max_output_tokens,
            deadline_seconds=min(cfg.max_network_seconds, deadline.remaining_work()),
            started_at=time.monotonic(),
        )
        policy = _provider_policy(cfg, options.ai_permitted_addresses)
        result = request_ai_proposals_via_transport(
            selection,
            policy,
            budget,
            credential=cfg.api_key,
            model=cfg.model,
        )
        transport_state = result.state
        proposals = result.proposals
        if not proposals and result.state != "ok":
            proposals = request_ai_proposals(report.findings, ctx, cfg, deadline)
    else:
        proposals = request_ai_proposals(report.findings, ctx, cfg, deadline)

    if proposals:
        report.execution["proposals"] = [
            {
                "kind": p.kind,
                "target_rule": p.target_rule,
                "target_span": p.target_span,
                "content": p.content,
                "model": p.model,
                "tokens_used": p.tokens_used,
            }
            for p in proposals
        ]
    if transport_state:
        report.execution["ai_transport_state"] = transport_state


def _attach_conversation_answer(
    report: FullReport,
    deadline: Deadline,
    record_limits: RecordLimits,
    options: ReviewExecutionOptions,
    digest: str,
    manifest: ContextManifest,
) -> None:
    convo = Conversation(report_digest=digest, head=report.contract.head, context_manifest=manifest)
    ai_result = None
    ai_enabled = bool(options.ai_config and options.ai_config.enabled)
    if ai_enabled and options.use_ai_transport and options.ai_config:
        cfg = options.ai_config
        selection = select_context(manifest, cfg.max_context_bytes)
        budget = AIBudget(
            max_requests=cfg.max_requests,
            context_bytes=cfg.max_context_bytes,
            output_tokens=cfg.max_output_tokens,
            deadline_seconds=min(cfg.max_network_seconds, deadline.remaining_work()),
            started_at=time.monotonic(),
        )
        policy = _provider_policy(cfg, options.ai_permitted_addresses)
        ai_result = invoke_for_conversation(
            selection,
            policy,
            budget,
            credential=cfg.api_key,
        )

    if ai_enabled and ai_result is None:
        convo_answer = answer(
            convo,
            options.conversation_question,
            digest,
            current_head=report.contract.head,
            report=report,
            limits=record_limits,
            ai_enabled=True,
        )
    elif not ai_enabled:
        convo_answer = deterministic_explanation(report, options.conversation_question)
    else:
        convo_answer = answer(
            convo,
            options.conversation_question,
            digest,
            current_head=report.contract.head,
            report=report,
            limits=record_limits,
            ai_enabled=True,
            ai_result=ai_result,
        )

    if convo_answer.text:
        report.execution.setdefault("conversation", [])
        report.execution["conversation"].append(
            {"state": convo_answer.state, "text": convo_answer.text},
        )


def observation_to_execution_record(obs: SecurityObservation) -> dict[str, Any]:
    return {
        "advisory": True,
        "rule": obs.rule,
        "claim": obs.claim,
        "model_version": obs.model_version,
        "path": obs.span.path,
        "start_line": obs.span.start_line,
        "end_line": obs.span.end_line,
        "boundaries": list(obs.boundaries),
    }


def collect_advisory_security_observations(
    repo: Path,
    paths: tuple[str, ...],
    head_blobs_by_path: dict[str, Any],
    head: str,
    policy_digest: str,
    limits: Limits,
    deadline: Deadline,
) -> list[dict[str, Any]]:
    """Run PYSEC001 advisory flow analysis; results stay outside canonical findings."""
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.endswith(".py"):
            continue
        blob = head_blobs_by_path.get(path)
        if blob is None:
            continue
        if deadline.is_work_exhausted():
            break
        try:
            source = read_blob(repo, blob.blob_oid, limits, deadline)
            ir = lower_python_source(source, limits=limits, deadline=deadline)
            bound = bind_statement_ir(
                ir,
                source_bytes=source,
                contract_digest=policy_digest,
                snapshot=head,
                path=path,
                side="head",
            )
            flow = analyze_python_security_flow(bound, limits=limits, deadline=deadline)
        except (ValueError, TimeoutError, SyntaxError):
            continue
        for obs in flow.observations:
            records.append(observation_to_execution_record(obs))
    return records


_SUFFIX_LANGUAGE: dict[str, str] = {
    ".go": "go",
    ".js": "typescript",
    ".jsx": "typescript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def dispatch_language_workers_for_changes(
    repo: Path,
    changed_paths: tuple[str, ...],
    head_blobs_by_path: dict[str, Any],
    head: str,
    policy_digest: str,
    registry: LanguageRegistry,
    limits: Limits,
    deadline: Deadline,
) -> list[dict[str, Any]]:
    """Dispatch optional language workers for non-Python changed paths."""
    serialized: list[dict[str, Any]] = []
    for path in changed_paths:
        if path.endswith(".py"):
            continue
        suffix = Path(path).suffix.lower()
        language = _SUFFIX_LANGUAGE.get(suffix)
        if language is None:
            continue
        blob = head_blobs_by_path.get(path)
        if blob is None:
            continue
        try:
            source = read_blob(repo, blob.blob_oid, limits, deadline)
        except Exception:
            continue
        entry = next(
            (e for e in registry.entries if e.language == language and e.capability == "syntax"),
            None,
        )
        grammar = entry.grammar_digest if entry is not None else ""
        request = LanguageRequest(
            contract_digest=policy_digest,
            scope_keys=(path,),
            language=language,
            grammar_digest=grammar,
            capability="syntax",
            source_blobs=((path, source),),
        )
        result = run_language(request, registry=registry, limits=limits, deadline=deadline)
        serialized.append(_language_result_record(path, result))
        if deadline.is_work_exhausted():
            break
    return serialized


def _language_result_record(path: str, result: LanguageResult) -> dict[str, Any]:
    return {
        "path": path,
        "contract_digest": result.contract_digest,
        "completed_keys": list(result.completed_keys),
        "unsupported": list(result.unsupported),
        "producer_digest": result.producer_digest,
        "content_fact_count": len(result.content_facts),
    }
