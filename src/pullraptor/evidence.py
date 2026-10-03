"""PullRaptor evidence accumulation, finding alignment, and policy decision logic."""

from __future__ import annotations

from pullraptor.models import (
    Config,
    CoverageReceipt,
    Diagnostic,
    Evidence,
    Finding,
    ReviewContract,
)


def accumulate(evidence: tuple[Evidence, ...]) -> tuple[bool, bool]:
    """Componentwise accumulation of independent evidence records.

    Requires identical claim_key and context.
    Returns (supported, refuted).
    """
    if not evidence:
        return (False, False)

    first = evidence[0]
    for e in evidence[1:]:
        if e.claim_key != first.claim_key or e.context != first.context:
            raise ValueError(
                f"Cannot accumulate evidence across different claims or contexts: "
                f"({first.claim_key}, {first.context}) vs ({e.claim_key}, {e.context})"
            )

    supported = any(e.supported for e in evidence)
    refuted = any(e.refuted for e in evidence)
    return (supported, refuted)


def align_findings(
    base: tuple[Finding, ...],
    head: tuple[Finding, ...],
    *,
    comparable: bool = True,
) -> tuple[Finding, ...]:
    """Conservative root-cause alignment of baseline and head findings.

    Opligation identity uses rule, version, obligation, anchor, and path.
    Position attributes (lines, columns, byte offsets) are omitted from matching.
    """
    if not comparable:
        return tuple(
            Finding(
                rule=f.rule,
                version=f.version,
                obligation=f.obligation,
                anchor=f.anchor,
                span=f.span,
                claim=f.claim,
                severity=f.severity,
                policy_class=f.policy_class,
                state=f.state,
                witness=f.witness,
                assumptions=f.assumptions,
                delta="unknown",
                evidence_delta="unknown",
            )
            for f in head
        )

    base_map: dict[tuple[str, str, str, str, str], Finding] = {
        (f.rule, f.version, f.obligation, f.anchor, f.span.path): f for f in base
    }

    aligned: list[Finding] = []
    for hf in head:
        key = (hf.rule, hf.version, hf.obligation, hf.anchor, hf.span.path)
        if key in base_map:
            bf = base_map[key]
            delta = "persisting"
            evidence_delta = "unchanged" if hf.witness == bf.witness else "changed"
        else:
            delta = "newly_detected"
            evidence_delta = "added"

        aligned.append(
            Finding(
                rule=hf.rule,
                version=hf.version,
                obligation=hf.obligation,
                anchor=hf.anchor,
                span=hf.span,
                claim=hf.claim,
                severity=hf.severity,
                policy_class=hf.policy_class,
                state=hf.state,
                witness=hf.witness,
                assumptions=hf.assumptions,
                delta=delta,
                evidence_delta=evidence_delta,
            )
        )

    return tuple(aligned)


def validate_receipts(
    contract: ReviewContract,
    receipts: tuple[CoverageReceipt, ...],
) -> tuple[Diagnostic, ...]:
    """Validate bijection between coordinator expected scope and worker receipts."""
    expected_map = {entry.key: entry for entry in contract.expected_scope}
    seen_keys: set[str] = set()
    diagnostics: list[Diagnostic] = []

    for r in receipts:
        if r.contract_digest != contract.policy_digest:
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_MISMATCH",
                    message=f"Receipt {r.key} contract digest mismatch: {r.contract_digest} != {contract.policy_digest}",
                    cause="contract_mismatch",
                )
            )

        if r.key in seen_keys:
            diagnostics.append(
                Diagnostic(
                    code="DUPLICATE_RECEIPT",
                    message=f"Duplicate receipt encountered for key: {r.key}",
                    cause="duplicate_receipt",
                )
            )
        seen_keys.add(r.key)

        if r.key not in expected_map:
            diagnostics.append(
                Diagnostic(
                    code="FOREIGN_RECEIPT",
                    message=f"Foreign receipt not present in expected scope: {r.key}",
                    cause="foreign_receipt",
                )
            )
        else:
            expected_entry = expected_map[r.key]
            if r.capability != expected_entry.capability:
                diagnostics.append(
                    Diagnostic(
                        code="CAPABILITY_MISMATCH",
                        message=f"Receipt capability {r.capability} does not match expected {expected_entry.capability}",
                        cause="capability_mismatch",
                    )
                )

    for expected_key in expected_map:
        if expected_key not in seen_keys:
            diagnostics.append(
                Diagnostic(
                    code="MISSING_RECEIPT",
                    message=f"Missing coverage receipt for expected key: {expected_key}",
                    cause="missing_receipt",
                )
            )

    return tuple(diagnostics)


def decide(
    contract: ReviewContract,
    receipts: tuple[CoverageReceipt, ...],
    findings: tuple[Finding, ...],
    diagnostics: tuple[Diagnostic, ...],
    config: Config,
) -> int:
    """Evaluate review policy and return process exit code.

    Exit codes:
    0: requested analysis complete with no configured blocking result
    1: complete with a configured blocker
    2: required analysis incomplete or unavailable
    3: tool/configuration/input failure
    """
    # 3: Check tool, configuration, or input failures
    fatal_causes = {"tool_failure", "config_failure", "input_failure"}
    for d in diagnostics:
        if d.cause in fatal_causes or d.code in ("TOOL_ERROR", "CONFIG_ERROR", "INPUT_ERROR"):
            return 3

    # 2: Check completeness of scope and analysis
    if not contract.discovery_complete:
        return 2

    # Receipt validation failure
    receipt_validation_codes = {
        "MISSING_RECEIPT", "DUPLICATE_RECEIPT", "FOREIGN_RECEIPT",
        "CONTRACT_MISMATCH", "CAPABILITY_MISMATCH",
    }
    for d in diagnostics:
        if d.code in receipt_validation_codes:
            return 2

    if len(receipts) != len(contract.expected_scope):
        return 2

    for r in receipts:
        if r.status != "complete":
            return 2

    for d in diagnostics:
        if d.code in ("PY_PARSE_FAILED", "IMPORT_UNRESOLVED", "DEADLINE_EXCEEDED", "LIMIT_EXCEEDED"):
            return 2

    # 1: Check for active blockers (must be supported and not conflicted)
    for f in findings:
        if f.policy_class == "blocker" and f.state == "supported":
            return 1

    # 0: Complete with no blockers
    return 0
