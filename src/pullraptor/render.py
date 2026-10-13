"""PullRaptor safe report renderers for Markdown, JSON, and SARIF."""

from __future__ import annotations

from dataclasses import asdict
from urllib.parse import quote

import html
import json
import re
from typing import Any

from pullraptor.models import (
    Deadline,
    FullReport,
    LimitFailure,
    LimitExceeded,
    encode_record,
    RecordLimits,
    Report,
    canonical_bytes,
)

_BIDI_AND_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def _sanitize_text(text: str) -> str:
    """Make controls visible without granting terminal authority."""
    sanitized = _BIDI_AND_CONTROL_RE.sub(lambda match: "\\r" if match[0] == "\r" else ("\\n" if match[0] == "\n" else f"\\u{ord(match[0]):04x}"), text)
    return sanitized


def _escape_md(text: str) -> str:
    """Safely escape text for Markdown rendering to prevent fence breakout and HTML injection."""
    sanitized = _sanitize_text(text)
    escaped_html = html.escape(sanitized)
    return re.sub(r"([`*{}_\[\]()!|])", r"\\\1", escaped_html)


def _check_deadline(report: Report, deadline: Deadline) -> None:
    expired = deadline.is_final_exhausted() if report.kind == "limit_failure" else deadline.is_work_exhausted()
    if expired:
        raise LimitExceeded("deadline_exceeded", "render_deadline", deadline.duration_seconds, None)


def _bounded_text(text: str, report: Report, limits: RecordLimits, deadline: Deadline) -> str:
    _check_deadline(report, deadline)
    cap = min(limits.max_payload_bytes, 16383) if report.kind == "limit_failure" else limits.max_payload_bytes - 1
    size = len(text.encode("utf-8"))
    if size > cap:
        raise LimitExceeded("report_limit_exceeded", "max_payload_bytes", cap, size)
    return text


def _path_uri(path: str) -> str:
    segments = path.split("/")
    if path.startswith("/") or any(segment in {".", ".."} for segment in segments):
        raise ValueError("SARIF location must be repository-relative")
    return "/".join(quote(segment, safe="") for segment in segments)


def render_markdown(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render a human-readable, injection-safe Markdown summary."""
    canonical_bytes(report, limits=limits, deadline=deadline)
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
        return _bounded_text("\n".join(lines), report, limits, deadline)

    assert isinstance(report, FullReport)
    contract = report.contract
    lines.append(f"**Revisions:** Base Tip `{_escape_md(contract.base_tip)}` | Comparison Base `{_escape_md(contract.comparison_base)}` | Head `{_escape_md(contract.head)}`")
    lines.append(f"**Profile:** `{contract.profile}` | **Status:** {'Complete' if contract.discovery_complete and all(r.status == 'complete' for r in report.receipts) else 'Partial'}\n")

    if contract.profile == "diff":
        lines.append("Semantic correctness and security were not evaluated.\n")

    # Scope and Coverage
    lines.append("## Scope & Coverage\n")
    lines.append(f"Coordinator discovery complete: {str(contract.discovery_complete).lower()}\n")
    lines.append("### Requested Scope\n")
    for entry in contract.expected_scope:
        lines.append(f"- `{_escape_md(entry.key)}` ({_escape_md(entry.capability)}): {_escape_md(entry.reason)}")
    lines.append("\n### Examined Receipts\n")
    if not report.receipts:
        lines.append("No files required analysis.\n")
    else:
        for r in report.receipts:
            status_symbol = "✓" if r.status == "complete" else "✗"
            lines.append(f"- [{status_symbol}] `{_escape_md(r.key)}` ({r.capability}): {r.status}")
            if r.cause:
                lines.append(f"  *Cause:* {_escape_md(r.cause)}")
            if r.recovery:
                lines.append(f"  *Recovery:* {_escape_md(r.recovery)}")
        lines.append("")

    # Findings
    lines.append("## Findings\n")
    if not report.findings:
        lines.append("No findings detected. Note: empty findings is not a safety or correctness claim.\n")
    else:
        for f in report.findings:
            span_str = f"{f.span.path}:{f.span.start_line}"
            lines.append(f"### [{_escape_md(f.rule)}] {_escape_md(f.obligation)} at `{_escape_md(span_str)}`\n")
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
            loc = f" (`{_escape_md(d.path)}`)" if d.path else ""
            lines.append(f"- **{d.code}**{loc}: {_escape_md(d.message)}")
        lines.append("")

    return _bounded_text("\n".join(lines), report, limits, deadline)


def render_json(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render canonical JSON bytes as UTF-8 string."""
    raw_bytes = canonical_bytes(report, limits=limits, deadline=deadline)
    return _bounded_text(raw_bytes.decode("utf-8"), report, limits, deadline)


def render_sarif(
    report: Report,
    *,
    limits: RecordLimits,
    deadline: Deadline,
) -> str:
    """Render report in standard SARIF 2.1.0 format."""
    canonical_bytes(report, limits=limits, deadline=deadline)
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
                            "toolExecutionNotifications": [{"level": "warning", "message": {"text": "Analysis incomplete; details omitted."}}],
                        }
                    ],
                    "results": [],
                    "properties": {"report": asdict(report)},
                }
            ],
        }
        encode_record(sarif_doc, limits)
        return _bounded_text(json.dumps(sarif_doc, sort_keys=True, indent=2), report, limits, deadline)

    assert isinstance(report, FullReport)
    rules_map: dict[str, dict[str, Any]] = {}
    sarif_results: list[dict[str, Any]] = []
    baseline_history: list[dict[str, Any]] = []

    for f in report.findings:
        if f.rule not in rules_map:
            rules_map[f.rule] = {
                "id": f.rule,
                "name": f.obligation,
                "shortDescription": {"text": f.claim},
            }

        level = "warning" if f.policy_class == "blocker" else "note"
        destination = baseline_history if f.span.side == "base" else sarif_results
        destination.append({
            "ruleId": f.rule,
            "level": level,
            "message": {"text": f.claim},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": _path_uri(f.span.path),
                            "uriBaseId": "%BASESRCROOT%" if f.span.side == "base" else "%HEADSRCROOT%",
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
                "side": f.span.side,
                "snapshot": report.contract.comparison_base if f.span.side == "base" else report.contract.head,
                "delta": f.delta,
                "evidence_delta": f.evidence_delta,
                "state": f.state,
                "witness": f.witness,
            },
        })

    is_success = report.contract.discovery_complete and report.execution.get("exit_code", 0) in (0, 1) and all(r.status == "complete" for r in report.receipts)
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
                "properties": {"report": json.loads(canonical_bytes(report, limits=limits, deadline=deadline)),
                               "baselineHistory": baseline_history},
            }
        ],
    }
    encode_record(sarif_doc, limits)
    return _bounded_text(json.dumps(sarif_doc, sort_keys=True, indent=2), report, limits, deadline)
