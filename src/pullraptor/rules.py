"""PullRaptor advisory rule pack (PY001, PY002, PY003)."""

from __future__ import annotations

from pullraptor.models import (
    Config,
    Finding,
    ResolvedFacts,
    Snapshot,
    Span,
)


def evaluate_rules(
    facts: tuple[ResolvedFacts, ...],
    snapshot: Snapshot,
    config: Config,
) -> tuple[Finding, ...]:
    """Evaluate advisory rules against resolved facts.

    All initial rules are advisory and factual; none claims an exploit or defect.
    """
    findings: list[Finding] = []

    for resolved in facts:
        bound = resolved.bound
        path = bound.path
        side = bound.side

        # Check whether standard library subprocess is genuinely resolved in this file
        has_stdlib_subprocess = any(
            (imp.get("canonical") == "subprocess" or imp.get("raw") == "subprocess")
            and imp.get("kind") == "stdlib"
            for imp in resolved.resolved_imports
        )

        for p in bound.content.pattern_facts:
            rule_id = p.get("rule")
            coords = p.get("coords", {})

            # Fallback coords if missing
            start_l = coords.get("start_line", 1)
            end_l = coords.get("end_line", start_l)
            start_b = coords.get("start_byte", 0)
            end_b = coords.get("end_byte", start_b)
            start_c = coords.get("start_column", 1)
            end_c = coords.get("end_column", start_c)

            span = Span(
                path=path,
                side=side,
                start_line=start_l,
                end_line=end_l,
                start_byte=start_b,
                end_byte=end_b,
                start_column=start_c,
                end_column=end_c,
            )

            if rule_id == "PY001":
                param = p.get("param", "parameter")
                findings.append(
                    Finding(
                        rule="PY001",
                        version="1.0",
                        obligation="mut_default",
                        anchor=param,
                        span=span,
                        claim="Default mutable argument can persist across omitted-argument calls",
                        severity="advisory",
                        policy_class="advisory",
                        state="supported",
                        witness=p.get("witness", f"Mutable default parameter {param}"),
                        assumptions=("no intentional caching",),
                        delta="newly_detected",
                        evidence_delta="added",
                    )
                )

            elif rule_id == "PY002":
                findings.append(
                    Finding(
                        rule="PY002",
                        version="1.0",
                        obligation="bare_except",
                        anchor="except",
                        span=span,
                        claim="Bare exception handler captures all exceptions including interruption",
                        severity="advisory",
                        policy_class="advisory",
                        state="supported",
                        witness=p.get("witness", "Bare exception handler with straight-line body"),
                        assumptions=("unintentional exception capture",),
                        delta="newly_detected",
                        evidence_delta="added",
                    )
                )

            elif rule_id == "PY003":
                # Ensure subprocess is truly resolved to stdlib
                if not has_stdlib_subprocess:
                    continue

                call_name = p.get("call", "run")
                findings.append(
                    Finding(
                        rule="PY003",
                        version="1.0",
                        obligation="subprocess_shell",
                        anchor=f"subprocess.{call_name}",
                        span=span,
                        claim="Subprocess invoked with shell=True",
                        severity="advisory",
                        policy_class="advisory",
                        state="supported",
                        witness=p.get("witness", f"subprocess.{call_name}(..., shell=True)"),
                        assumptions=("shell invocation intended",),
                        delta="newly_detected",
                        evidence_delta="added",
                    )
                )

    return tuple(findings)
