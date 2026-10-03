"""PullRaptor command-line interface entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from pullraptor.git_snapshot import freeze_working_tree
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

    args = parser.parse_args(argv)

    start_monotonic = time.monotonic()
    repo_path = Path(args.repo).resolve()

    overrides: dict[str, object] = {}
    if args.profile:
        overrides["profile"] = args.profile

    try:
        if args.staged or args.workdir:
            base_ref = args.base if args.base is not None else "HEAD"
            is_head_tree = True
            head_ref = freeze_working_tree(
                repo=repo_path,
                limits=Limits(),
                deadline=Deadline(started_at=start_monotonic, duration_seconds=10.0),
                staged_only=args.staged,
            )
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
