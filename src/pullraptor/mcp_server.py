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

from pullraptor.local_snapshot import resolve_local_review_refs
from pullraptor.kernel import review
from pullraptor.models import Deadline, FullReport, Limits, RecordLimits, Report
from pullraptor.mcp_sessions import (
    MAX_RESPONSE_BYTES,
    MCPSession,
    PROTOCOL_VERSION,
    default_deadline,
    get_session_report,
    negotiate_protocol_version,
    register_session_report,
    reject_unknown_fields,
    validate_request_bytes,
)
from pullraptor.render import render_json, render_markdown

SERVER_NAME = "pullraptor-mcp"
SERVER_VERSION = "0.3.0"

_DEFAULT_SESSION = MCPSession(id="default", workspace_grants=frozenset({"*"}))

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
                    "include_untracked": {
                        "type": "boolean",
                        "description": "When reviewing workdir, opt in to admitting untracked files (default false)",
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
                    "report_digest": {"type": "string", "description": "Pinned report digest from pullraptor_review"},
                    "repository_id": {
                        "type": "string",
                        "description": "Authorized repository identity for the pinned report",
                    },
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
                    "report_digest": {"type": "string", "description": "Pinned report digest from pullraptor_review"},
                    "repository_id": {
                        "type": "string",
                        "description": "Authorized repository identity for the pinned report",
                    },
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
                    "report_digest": {"type": "string", "description": "Pinned report digest from pullraptor_review"},
                    "repository_id": {
                        "type": "string",
                        "description": "Authorized repository identity for the pinned report",
                    },
                    "use_ai": {
                        "type": "boolean",
                        "description": "Request optional advisory model explanation when AI endpoint is configured",
                    },
                },
                "required": ["rule_id"],
            },
        },
    ]


def _authorized_repository_id(repo_path: Path) -> str:
    explicit = os.environ.get("PULLRAPTOR_MCP_REPOSITORY_ID", "").strip()
    if explicit:
        return explicit
    return str(repo_path.resolve())


def _active_session(session: MCPSession | None = None) -> MCPSession:
    return session or _DEFAULT_SESSION


def handle_review(args: dict[str, Any], *, session: MCPSession | None = None) -> str:
    mcp_session = _active_session(session)
    if mcp_session.active_reviews >= 2:
        return json.dumps({"status": "review_cap_exceeded", "message": "At most 2 active reviews per session"})
    mcp_session.active_reviews += 1
    repo_path = _validate_repo_path(args.get("repo_path"))
    start_monotonic = time.monotonic()
    staged = bool(args.get("staged"))
    workdir = bool(args.get("workdir"))
    include_untracked = bool(args.get("include_untracked"))
    head = args.get("head")
    base = args.get("base")
    profile = args.get("profile")

    overrides: dict[str, Any] = {}
    if profile:
        overrides["profile"] = profile

    limits = Limits()
    deadline = Deadline(started_at=start_monotonic, duration_seconds=10.0)

    if staged or workdir:
        local = resolve_local_review_refs(
            repo_path,
            staged_only=staged,
            include_untracked=include_untracked,
            base_ref=base,
            limits=limits,
            deadline=deadline,
        )
        snapshot = local.snapshot
        if not snapshot.discovery_complete or not snapshot.tree_oid:
            return json.dumps(
                {
                    "status": "capture_incomplete",
                    "diagnostics": [
                        {"code": d.code, "message": d.message, "cause": d.cause}
                        for d in snapshot.diagnostics
                    ],
                }
            )
        base_ref = local.base_ref
        head_ref = local.head_ref
        is_head_tree = local.is_head_tree
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

    repository_id = _authorized_repository_id(repo_path)
    head_or_snapshot = head_ref if isinstance(head_ref, str) else str(head_ref)
    pinned = register_session_report(
        mcp_session,
        authorized_repository_id=repository_id,
        report=rep,
        head_or_snapshot=head_or_snapshot,
        limits=rec_limits,
        deadline=deadline,
    )
    mcp_session.active_reviews = max(0, mcp_session.active_reviews - 1)

    markdown = render_markdown(rep, limits=rec_limits, deadline=deadline)
    return (
        markdown
        + f"\n\n<!-- pullraptor:report_digest={pinned.report_digest} repository_id={repository_id} -->\n"
    )


def _resolve_report_from_args(
    args: dict[str, Any],
    *,
    session: MCPSession,
) -> tuple[Report | None, str]:
    digest = str(args.get("report_digest", "")).strip()
    repository_id = str(args.get("repository_id", "")).strip()
    if not digest or not repository_id:
        return None, "report_not_found"
    pinned = get_session_report(session.id, digest, repository_id, session=session)
    if pinned is None:
        return None, "report_not_found"
    return pinned.report, "ok"


def handle_get_findings(args: dict[str, Any], *, session: MCPSession | None = None) -> str:
    mcp_session = _active_session(session)
    rep, state = _resolve_report_from_args(args, session=mcp_session)
    if rep is None:
        return json.dumps({"status": state, "findings": [], "implicit_review_count": 0})

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


def handle_get_coverage(args: dict[str, Any], *, session: MCPSession | None = None) -> str:
    mcp_session = _active_session(session)
    rep, state = _resolve_report_from_args(args, session=mcp_session)
    if rep is None:
        return json.dumps({"status": state, "receipts": []})

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


def handle_explain(args: dict[str, Any], *, session: MCPSession | None = None) -> str:
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

    mcp_session = _active_session(session)
    rep, _state = _resolve_report_from_args(args, session=mcp_session)
    related: tuple[Any, ...] = ()
    if isinstance(rep, FullReport):
        related = tuple(f for f in rep.findings if f.rule == rule_id)

    prompt = build_explanation_prompt(
        related,
        ExternalContext(issue_text=f"Explain rule {rule_id} for developers."),
        max_bytes=ai_cfg.max_context_bytes,
    )
    deadline = default_deadline()
    proposals = query_ai_provider(ai_cfg, prompt, deadline=deadline)
    if not proposals:
        return base_text

    return (
        base_text
        + "\n---\n### Advisory Model Explanation (Untrusted)\n\n"
        + proposals[0].content
        + "\n"
    )


def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    session: MCPSession | None = None,
) -> dict[str, Any]:
    try:
        if name == "pullraptor_review":
            text = handle_review(arguments, session=session)
        elif name == "pullraptor_get_findings":
            text = handle_get_findings(arguments, session=session)
        elif name == "pullraptor_get_coverage":
            text = handle_get_coverage(arguments, session=session)
        elif name == "pullraptor_explain_finding":
            text = handle_explain(arguments, session=session)
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as exc:
        return {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}


def process_request(req: dict[str, Any], *, session: MCPSession | None = None) -> dict[str, Any] | None:
    mcp_session = _active_session(session)
    msg_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    # Notification handling (no response)
    if method == "notifications/initialized":
        mcp_session.initialized = True
        return None

    if method == "initialize":
        init_params = params if isinstance(params, dict) else {}
        if reject_unknown_fields(init_params, frozenset({"protocolVersion", "capabilities", "clientInfo"})):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": "unknown_fields"},
            }
        negotiated, err = negotiate_protocol_version(init_params.get("protocolVersion"))
        if err:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": err},
            }
        mcp_session.negotiated_version = negotiated
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": negotiated,
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
        if mcp_session.negotiated_version is None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32002, "message": "session_not_initialized"},
            }
        name = params.get("name", "")
        args = params.get("arguments") or {}
        result = dispatch_tool(name, args, session=mcp_session)
        encoded = json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result})
        if len(encoded.encode("utf-8")) > MAX_RESPONSE_BYTES:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": "response_too_large"},
            }
        return json.loads(encoded)

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
        digest = str(params.get("report_digest", "")).strip()
        repository_id = str(params.get("repository_id", "")).strip()
        rep: Report | None = None
        if digest and repository_id:
            pinned = get_session_report(mcp_session.id, digest, repository_id, session=mcp_session)
            if pinned is not None:
                rep = pinned.report
        if uri == "pullraptor://report/latest" and rep is not None:
            limits = RecordLimits()
            content = render_json(rep, limits=limits, deadline=default_deadline())
        elif uri == "pullraptor://coverage/summary" and isinstance(rep, FullReport):
            content = handle_get_coverage(
                {"report_digest": digest, "repository_id": repository_id},
                session=mcp_session,
            )
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


def handle_message(payload: bytes, session: MCPSession | None = None) -> bytes | None:
    """Parse one bounded MCP request and return encoded JSON-RPC response bytes."""
    mcp_session = _active_session(session)
    err = validate_request_bytes(payload)
    if err:
        return json.dumps(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": err}}
        ).encode("utf-8")
    req = json.loads(payload.decode("utf-8"))
    if not isinstance(req, dict):
        return json.dumps(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid_request"}}
        ).encode("utf-8")
    resp = process_request(req, session=mcp_session)
    if resp is None:
        return None
    encoded = json.dumps(resp).encode("utf-8")
    if len(encoded) > MAX_RESPONSE_BYTES:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32603, "message": "response_too_large"},
            }
        ).encode("utf-8")
    return encoded


def run_mcp_server(input_stream=None, output_stream=None, *, session: MCPSession | None = None) -> int:
    """Run the MCP server event loop over standard IO streams."""
    instream = input_stream or sys.stdin
    outstream = output_stream or sys.stdout
    mcp_session = _active_session(session)

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

        raw = json.dumps(req).encode("utf-8")
        resp_bytes = handle_message(raw, session=mcp_session)
        if resp_bytes is not None:
            outstream.write(resp_bytes.decode("utf-8") + "\n")
            outstream.flush()

    return 0


if __name__ == "__main__":
    sys.exit(run_mcp_server())
