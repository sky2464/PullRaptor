"""Model Context Protocol (MCP) server for PullRaptor.

Implements a standard-library stdio JSON-RPC 2.0 server providing bounded tools
and resources for AI assistants and code editors.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from pullraptor.git_snapshot import freeze_working_tree
from pullraptor.kernel import review
from pullraptor.models import Deadline, FullReport, Limits, RecordLimits, Report
from pullraptor.render import render_json, render_markdown

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "pullraptor-mcp"
SERVER_VERSION = "0.3.0"

# In-memory store for latest review state
_STATE: dict[str, Any] = {
    "report": None,
    "deadline": None,
    "limits": None,
    "repo_path": None,
}

RULE_EXPLANATIONS: dict[str, dict[str, str]] = {
    "PY001": {
        "title": "Default Mutable Parameter (mut_default)",
        "claim": "Default mutable argument can persist across omitted-argument calls.",
        "rationale": "In Python, default parameter expressions are evaluated once when the function is defined, not per invocation. Mutating the parameter modifies the object shared across all subsequent calls.",
        "remediation": "Replace default mutable values (such as [] or {}) with None, and initialize the collection inside the function body (e.g., `items = [] if items is None else items`).",
    },
    "PY002": {
        "title": "Bare Except Handler (bare_except)",
        "claim": "Bare exception handler captures all exceptions including interruption.",
        "rationale": "Using `except:` without an exception class catches `BaseException`, including `KeyboardInterrupt`, `SystemExit`, and generator exits, masking bugs and preventing graceful process termination.",
        "remediation": "Catch explicit exception types, or catch `Exception` if general error trapping is intended: `except Exception as err:`.",
    },
    "PY003": {
        "title": "Subprocess Shell Invocation (subprocess_shell)",
        "claim": "Subprocess invoked with shell=True.",
        "rationale": "Spawning a subshell with `shell=True` increases risk of command injection when inputs are derived from untrusted sources or arguments containing shell metacharacters.",
        "remediation": "Pass commands as an argument sequence (list of strings) and omit `shell=True`: `subprocess.run(['git', 'status'], check=True)`.",
    },
}


def _workspace_root() -> Path:
    """Authorized workspace boundary for MCP repository path arguments."""
    env_root = os.environ.get("PULLRAPTOR_MCP_WORKSPACE_ROOT")
    if env_root:
        return Path(os.path.realpath(env_root))
    return Path(os.path.realpath(os.getcwd()))


def _validate_repo_path(repo_arg: str | None) -> Path:
    """Validate and resolve repository path safely within the workspace boundary."""
    raw = repo_arg or "."
    path = Path(os.path.realpath(raw))
    workspace = _workspace_root()
    try:
        path.relative_to(workspace)
    except ValueError:
        raise ValueError(f"Path is outside authorized workspace boundary: {raw}") from None
    if not path.is_dir():
        raise ValueError(f"Path is not a valid directory: {raw}")
    if not (path / ".git").exists():
        raise ValueError(f"Path is not a Git repository root: {raw}")
    return path


_SEVERITY_ORDER = {"advisory": 0, "warning": 1, "error": 2}


def _load_optional_ai_config() -> Any:
    from pullraptor.ai_adapter import AIConfig

    endpoint = os.environ.get("PULLRAPTOR_AI_ENDPOINT", "").strip()
    if not endpoint:
        return None
    return AIConfig(
        enabled=True,
        endpoint=endpoint,
        api_key=os.environ.get("PULLRAPTOR_AI_TOKEN", ""),
        model=os.environ.get("PULLRAPTOR_AI_MODEL", "default"),
    )


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "pullraptor_review",
            "description": "Run deterministic static analysis on Git revisions, staged index, or uncommitted workdir changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to Git repository root (default: current directory)",
                    },
                    "base": {
                        "type": "string",
                        "description": "Base Git reference or commit OID (default: HEAD~1 for commit review, HEAD for staged/workdir)",
                    },
                    "head": {
                        "type": "string",
                        "description": "Head Git reference or commit OID",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "Review staged index changes against base",
                    },
                    "workdir": {
                        "type": "boolean",
                        "description": "Review uncommitted working tree changes against base",
                    },
                    "profile": {
                        "type": "string",
                        "enum": ["structural", "diff"],
                        "description": "Review profile",
                    },
                },
            },
        },
        {
            "name": "pullraptor_get_findings",
            "description": "Retrieve and filter findings from the latest review.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to Git repository root"},
                    "min_severity": {
                        "type": "string",
                        "enum": ["advisory", "warning", "error"],
                        "description": "Minimum finding severity",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Substring or path filter for findings",
                    },
                },
            },
        },
        {
            "name": "pullraptor_get_coverage",
            "description": "Retrieve verification receipts, analysis scope, and coverage breakdown.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to Git repository root"},
                },
            },
        },
        {
            "name": "pullraptor_explain_finding",
            "description": "Provide detailed rule explanation and remediation guidance for a specific finding.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "Rule identifier (e.g., PY001, PY002, PY003)"},
                    "finding_id": {"type": "string", "description": "Finding identifier from review results"},
                    "use_ai": {
                        "type": "boolean",
                        "description": "Request optional advisory model explanation when AI endpoint is configured",
                    },
                },
                "required": ["rule_id"],
            },
        },
    ]


def handle_review(args: dict[str, Any]) -> str:
    repo_path = _validate_repo_path(args.get("repo_path"))
    start_monotonic = time.monotonic()
    staged = bool(args.get("staged"))
    workdir = bool(args.get("workdir"))
    head = args.get("head")
    base = args.get("base")
    profile = args.get("profile")

    overrides: dict[str, Any] = {}
    if profile:
        overrides["profile"] = profile

    if staged or workdir:
        base_ref = base if base is not None else "HEAD"
        is_head_tree = True
        head_ref = freeze_working_tree(
            repo=repo_path,
            limits=Limits(),
            deadline=Deadline(started_at=start_monotonic, duration_seconds=10.0),
            staged_only=staged,
        )
    else:
        head_ref = head if head is not None else "HEAD"
        base_ref = base if base is not None else "HEAD~1"
        is_head_tree = False

    rep, deadline, rec_limits = review(
        repo=repo_path,
        base_ref=base_ref,
        head_ref=head_ref,
        overrides=overrides,
        started_at=start_monotonic,
        is_head_tree=is_head_tree,
    )

    _STATE["report"] = rep
    _STATE["deadline"] = deadline
    _STATE["limits"] = rec_limits
    _STATE["repo_path"] = str(repo_path)

    return render_markdown(rep, limits=rec_limits, deadline=deadline)


def handle_get_findings(args: dict[str, Any]) -> str:
    rep: Report | None = _STATE.get("report")
    if rep is None:
        # Run review automatically
        handle_review(args)
        rep = _STATE.get("report")

    if not isinstance(rep, FullReport):
        return json.dumps({"status": "no_full_report", "findings": []})

    findings_out = []
    file_pat = args.get("file_pattern", "")
    min_severity = str(args.get("min_severity", "advisory")).lower()
    min_rank = _SEVERITY_ORDER.get(min_severity, 0)
    for f in rep.findings:
        if file_pat and file_pat not in f.span.path:
            continue
        if _SEVERITY_ORDER.get(f.severity, 0) < min_rank:
            continue
        findings_out.append(
            {
                "rule": f.rule,
                "path": f.span.path,
                "start_line": f.span.start_line,
                "end_line": f.span.end_line,
                "severity": f.severity,
                "claim": f.claim,
                "witness": f.witness,
                "anchor": f.anchor,
            }
        )
    return json.dumps({"count": len(findings_out), "findings": findings_out}, indent=2)


def handle_get_coverage(args: dict[str, Any]) -> str:
    rep: Report | None = _STATE.get("report")
    if rep is None:
        handle_review(args)
        rep = _STATE.get("report")

    if not isinstance(rep, FullReport):
        return json.dumps({"status": "no_full_report", "receipts": []})

    complete = all(r.status == "complete" for r in rep.receipts)
    receipts_out = [
        {
            "key": r.key,
            "capability": r.capability,
            "status": r.status,
            "cause": r.cause,
            "recovery": r.recovery,
        }
        for r in rep.receipts
    ]
    return json.dumps(
        {
            "status": "complete" if complete else "partial",
            "receipt_count": len(rep.receipts),
            "complete_count": sum(1 for r in rep.receipts if r.status == "complete"),
            "gap_count": sum(1 for r in rep.receipts if r.status != "complete"),
            "receipts": receipts_out,
        },
        indent=2,
    )


def handle_explain(args: dict[str, Any]) -> str:
    rule_id = str(args.get("rule_id", "")).strip().upper()
    info = RULE_EXPLANATIONS.get(rule_id)
    if not info:
        return f"No documentation found for rule {rule_id}. Available rules: {', '.join(sorted(RULE_EXPLANATIONS.keys()))}."

    base_text = (
        f"### {rule_id}: {info['title']}\n\n"
        f"**Claim**: {info['claim']}\n\n"
        f"**Rationale**: {info['rationale']}\n\n"
        f"**Remediation**:\n{info['remediation']}\n"
    )

    if not args.get("use_ai"):
        return base_text

    ai_cfg = _load_optional_ai_config()
    if ai_cfg is None:
        return base_text + "\n> Advisory model explanation unavailable: set PULLRAPTOR_AI_ENDPOINT to enable.\n"

    from pullraptor.ai_adapter import ExternalContext, build_explanation_prompt, query_ai_provider
    from pullraptor.models import Deadline

    rep: Report | None = _STATE.get("report")
    related: tuple[Any, ...] = ()
    if isinstance(rep, FullReport):
        related = tuple(f for f in rep.findings if f.rule == rule_id)

    prompt = build_explanation_prompt(
        related,
        ExternalContext(issue_text=f"Explain rule {rule_id} for developers."),
        max_bytes=ai_cfg.max_context_bytes,
    )
    deadline = _STATE.get("deadline") or Deadline(time.monotonic(), 60.0)
    proposals = query_ai_provider(ai_cfg, prompt, deadline=deadline)
    if not proposals:
        return base_text

    return (
        base_text
        + "\n---\n### Advisory Model Explanation (Untrusted)\n\n"
        + proposals[0].content
        + "\n"
    )


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "pullraptor_review":
            text = handle_review(arguments)
        elif name == "pullraptor_get_findings":
            text = handle_get_findings(arguments)
        elif name == "pullraptor_get_coverage":
            text = handle_get_coverage(arguments)
        elif name == "pullraptor_explain_finding":
            text = handle_explain(arguments)
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as exc:
        return {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}


def process_request(req: dict[str, Any]) -> dict[str, Any] | None:
    msg_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    # Notification handling (no response)
    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _tool_definitions()}}

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        result = dispatch_tool(name, args)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "resources": [
                    {
                        "uri": "pullraptor://report/latest",
                        "name": "Latest Review Report",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": "pullraptor://coverage/summary",
                        "name": "Latest Coverage Summary",
                        "mimeType": "application/json",
                    },
                ]
            },
        }

    if method == "resources/read":
        uri = params.get("uri", "")
        rep: Report | None = _STATE.get("report")
        if uri == "pullraptor://report/latest" and rep is not None:
            content = render_json(rep, limits=_STATE.get("limits") or RecordLimits(), deadline=_STATE.get("deadline") or Deadline(time.monotonic(), 60.0))
        elif uri == "pullraptor://coverage/summary" and isinstance(rep, FullReport):
            content = handle_get_coverage({})
        else:
            content = json.dumps({"error": f"Resource not found or no active report: {uri}"})

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "contents": [{"uri": uri, "mimeType": "application/json", "text": content}]
            },
        }

    # Unknown method
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def run_mcp_server(input_stream=None, output_stream=None) -> int:
    """Run the MCP server event loop over standard IO streams."""
    instream = input_stream or sys.stdin
    outstream = output_stream or sys.stdout

    while True:
        line = instream.readline()
        if not line:
            break
        line_str = line.strip()
        if not line_str:
            continue

        # Support Content-Length prefix if present
        if line_str.lower().startswith("content-length:"):
            try:
                length = int(line_str.split(":", 1)[1].strip())
                # Read delimiter empty line
                instream.readline()
                raw_body = instream.read(length)
                req = json.loads(raw_body)
            except Exception:
                continue
        else:
            try:
                req = json.loads(line_str)
            except Exception:
                continue

        resp = process_request(req)
        if resp is not None:
            outstream.write(json.dumps(resp) + "\n")
            outstream.flush()

    return 0


if __name__ == "__main__":
    sys.exit(run_mcp_server())
