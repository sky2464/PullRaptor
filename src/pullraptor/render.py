"""PullRaptor safe report renderers for Markdown, JSON, and SARIF."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from pullraptor.models import (
    Deadline,
    FullReport,
    LimitFailure,
    RecordLimits,
    Report,
    canonical_bytes,
)

_BIDI_AND_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def _sanitize_text(text: str) -> str:
    """Strip terminal escape codes and bidi override characters."""
    sanitized = _BIDI_AND_CONTROL_RE.sub("", text)
    return sanitized


def _escape_md(text: str) -> str:
    """Safely escape text for Markdown rendering to prevent fence breakout and HTML injection."""
    sanitized = _sanitize_text(text)
    escaped_html = html.escape(sanitized)
    return escaped_html.replace("```", "\\`\\`\\`")


def render_markdown(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render a human-readable, injection-safe Markdown summary."""
    lines: list[str] = ["# PullRaptor Review\n"]

    if report.kind == "limit_failure":
        assert isinstance(report, LimitFailure)
        lines.append("## Analysis Limit Exceeded\n")
        lines.append("- **Analysis Complete:** false")
        lines.append("- **Exit Code:** 2")
        lines.append(f"- **Cause:** {_escape_md(report.cause)}")
        if report.limit:
            lines.append(f"- **Limit:** {_escape_md(str(report.limit))}")
        lines.append("\n*Note: Review details were omitted to guarantee bounded resource consumption.*")
        return "\n".join(lines)

    assert isinstance(report, FullReport)
    contract = report.contract
    lines.append(f"**Revisions:** Base `{contract.comparison_base[:12]}` → Head `{contract.head[:12]}`")
    lines.append(f"**Profile:** `{contract.profile}` | **Status:** {'Complete' if all(r.status == 'complete' for r in report.receipts) else 'Partial'}\n")

    # Scope and Coverage
    lines.append("## Scope & Coverage\n")
    if not report.receipts:
        lines.append("No files required analysis.\n")
    else:
        for r in report.receipts:
            status_symbol = "✓" if r.status == "complete" else "✗"
            lines.append(f"- [{status_symbol}] `{_escape_md(r.key)}` ({r.capability}): {r.status}")
            if r.cause:
                lines.append(f"  *Cause:* {_escape_md(r.cause)}")
        lines.append("")

    # Findings
    lines.append("## Findings\n")
    if not report.findings:
        lines.append("No findings detected. Note: empty findings is not a safety or correctness claim.\n")
    else:
        for f in report.findings:
            span_str = f"{f.span.path}:{f.span.start_line}"
            lines.append(f"### [{f.rule}] {f.obligation} at `{span_str}`\n")
            lines.append(f"- **Claim:** {_escape_md(f.claim)}")
            lines.append(f"- **Severity:** {f.severity} ({f.policy_class}) | **Delta:** {f.delta}")
            lines.append(f"- **Witness:**\n```\n{_escape_md(f.witness)}\n```\n")

    # AI Untrusted Proposals
    proposals = report.execution.get("proposals", []) if isinstance(report.execution, dict) else []
    if proposals:
        lines.append("## AI Explanations & Suggestions (Untrusted Proposals)\n")
        lines.append("> [!NOTE]\n> The following explanations are model-generated and untrusted. They do not alter deterministic review findings or grant merge authorization.\n")
        for p in proposals:
            lines.append(f"### Model Explanation (`{_escape_md(str(p.get('model', 'unknown')))}`)\n")
            lines.append(f"{_escape_md(str(p.get('content', '')))}\n")

    # Diagnostics
    if report.diagnostics:
        lines.append("## Diagnostics\n")
        for d in report.diagnostics:
            loc = f" (`{d.path}`)" if d.path else ""
            lines.append(f"- **{d.code}**{loc}: {_escape_md(d.message)}")
        lines.append("")

    return "\n".join(lines)


def render_json(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render canonical JSON bytes as UTF-8 string."""
    raw_bytes = canonical_bytes(report, limits=limits, deadline=deadline)
    return raw_bytes.decode("utf-8")


def render_sarif(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render report in standard SARIF 2.1.0 format."""
    if report.kind == "limit_failure":
        sarif_doc = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "PullRaptor",
                            "semanticVersion": "0.1.0",
                            "rules": [],
                        }
                    },
                    "invocations": [
                        {
                            "executionSuccessful": False,
                            "exitCode": 2,
                        }
                    ],
                    "results": [],
                }
            ],
        }
        return json.dumps(sarif_doc, sort_keys=True, indent=2)

    assert isinstance(report, FullReport)
    rules_map: dict[str, dict[str, Any]] = {}
    sarif_results: list[dict[str, Any]] = []

    for f in report.findings:
        if f.rule not in rules_map:
            rules_map[f.rule] = {
                "id": f.rule,
                "name": f.obligation,
                "shortDescription": {"text": f.claim},
            }

        level = "warning" if f.policy_class == "blocker" else "note"
        sarif_results.append({
            "ruleId": f.rule,
            "level": level,
            "message": {"text": f.claim},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f.span.path,
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": f.span.start_line,
                            "endLine": f.span.end_line,
                            "startColumn": f.span.start_column,
                            "endColumn": f.span.end_column,
                            "byteOffset": f.span.start_byte,
                            "byteLength": max(0, f.span.end_byte - f.span.start_byte),
                        },
                    }
                }
            ],
            "properties": {
                "delta": f.delta,
                "evidence_delta": f.evidence_delta,
                "state": f.state,
                "witness": f.witness,
            },
        })

    is_success = report.execution.get("exit_code", 0) in (0, 1) and all(r.status == "complete" for r in report.receipts)
    sarif_doc = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "PullRaptor",
                        "semanticVersion": "0.1.0",
                        "rules": list(rules_map.values()),
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": is_success,
                        "exitCode": report.execution.get("exit_code", 0),
                    }
                ],
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(sarif_doc, sort_keys=True, indent=2)
