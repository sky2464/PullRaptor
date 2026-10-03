"""PullRaptor command-line interface entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from pullraptor.git_snapshot import resolve_inputs
from pullraptor.local_snapshot import capture_local
from pullraptor.kernel import review
from pullraptor.models import Deadline, Limits
from pullraptor.render import render_json, render_markdown, render_sarif


def main(argv: list[str] | None = None) -> int:
    """CLI main function returning process exit code."""
    parser = argparse.ArgumentParser(
        prog="pullraptor",
        description="PullRaptor offline review kernel",
    )
    parser.add_argument("--repo", default=".", help="Path to Git repository root (default: current directory)")
    parser.add_argument("--base", default=None, help="Base Git ref or commit OID (default: HEAD~1 for commit review, HEAD for working tree)")

    head_group = parser.add_mutually_exclusive_group()
    head_group.add_argument("--head", help="Head Git ref or commit OID")
    head_group.add_argument("--staged", action="store_true", help="Review staged index changes against base (default: HEAD)")
    head_group.add_argument("--workdir", action="store_true", help="Review uncommitted working tree changes against base (default: HEAD)")

    parser.add_argument("--exact-base", action="store_true", help="Compare exact base commit instead of computing merge base")
    parser.add_argument("--profile", choices=["structural", "diff"], default=None, help="Review profile ('structural' or 'diff')")
    parser.add_argument("--format", choices=["markdown", "json", "sarif"], default="markdown", help="Output format ('markdown', 'json', 'sarif')")
    parser.add_argument("--no-cache", action="store_true", help="Disable parser caching")
    parser.add_argument("--ci", action="store_true", help="Run in CI mode with strict verification")

    # Optional AI context and explanations
    parser.add_argument("--ai-endpoint", help="HTTPS endpoint for optional AI explanations")
    parser.add_argument("--ai-model", default="default", help="Model name for AI explanations")
    parser.add_argument("--ai-token", help="Bearer token for AI endpoint (or env PULLRAPTOR_AI_TOKEN)")
    parser.add_argument("--context-issue", help="File containing issue/PR description text for untrusted context")
    parser.add_argument("--context-ci-log", help="File containing CI failure log snippet for untrusted context")

    # MCP server mode
    parser.add_argument("--mcp", action="store_true", help="Start Model Context Protocol (MCP) stdio server")

    # If first argument is 'mcp', run MCP server directly
    raw_args = argv if argv is not None else sys.argv[1:]
    if raw_args and raw_args[0] == "mcp":
        from pullraptor.mcp_server import run_mcp_server
        return run_mcp_server()

    args = parser.parse_args(argv)

    if args.mcp:
        from pullraptor.mcp_server import run_mcp_server
        return run_mcp_server()

    start_monotonic = time.monotonic()
    repo_path = Path(args.repo).resolve()

    overrides: dict[str, object] = {}
    if args.profile:
        overrides["profile"] = args.profile

    try:
        if args.staged or args.workdir:
            base_ref = args.base if args.base is not None else "HEAD"
            is_head_tree = True
            limits = Limits()
            deadline = Deadline(started_at=start_monotonic, duration_seconds=10.0)
            base_tip, _, _ = resolve_inputs(
                repo_path,
                base_ref,
                "HEAD",
                limits,
                deadline,
                exact_base=True,
            )
            snapshot = capture_local(
                repo_path,
                base_tip,
                staged_only=args.staged,
                include_untracked=False,
                limits=limits,
                deadline=deadline,
            )
            if not snapshot.discovery_complete or not snapshot.tree_oid:
                sys.stderr.write("PullRaptor: local snapshot capture incomplete\n")
                for diag in snapshot.diagnostics:
                    sys.stderr.write(f"  - {diag.code}: {diag.message}\n")
                return 2
            head_ref = snapshot.tree_oid
        else:
            if not args.head:
                parser.error("One of --head, --staged, or --workdir is required")
            head_ref = args.head
            base_ref = args.base if args.base is not None else "HEAD~1"
            is_head_tree = False

        report, deadline, record_limits = review(
            repo=repo_path,
            base_ref=base_ref,
            head_ref=head_ref,
            overrides=overrides,
            started_at=start_monotonic,
            ci=args.ci,
            exact_base=args.exact_base,
            use_cache=not args.no_cache,
            is_head_tree=is_head_tree,
        )
    except Exception as err:
        sys.stderr.write(f"PullRaptor: fatal execution error: {err}\n")
        return 3

    # Optional AI Context & Explanations (Untrusted Proposals)
    if args.ai_endpoint and report.kind == "full" and report.findings:
        from pullraptor.ai_adapter import (
            AIConfig,
            ExternalContext,
            request_ai_proposals,
        )

        issue_text = ""
        if args.context_issue and Path(args.context_issue).exists():
            issue_text = Path(args.context_issue).read_text(encoding="utf-8", errors="replace")

        ci_log = ""
        if args.context_ci_log and Path(args.context_ci_log).exists():
            ci_log = Path(args.context_ci_log).read_text(encoding="utf-8", errors="replace")

        ext_ctx = ExternalContext(issue_text=issue_text, ci_log_snippet=ci_log)
        ai_cfg = AIConfig(
            enabled=True,
            endpoint=args.ai_endpoint,
            model=args.ai_model,
            api_key=args.ai_token or os.environ.get("PULLRAPTOR_AI_TOKEN", ""),
        )

        proposals = request_ai_proposals(report.findings, ext_ctx, ai_cfg, deadline)
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

    # Render report to stdout
    if args.format == "json":
        rendered = render_json(report, limits=record_limits, deadline=deadline)
    elif args.format == "sarif":
        rendered = render_sarif(report, limits=record_limits, deadline=deadline)
    else:
        rendered = render_markdown(report, limits=record_limits, deadline=deadline)

    sys.stdout.write(rendered + "\n")

    if report.kind == "full":
        exit_code = report.execution.get("exit_code", 0)
    else:
        exit_code = report.exit_code

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
