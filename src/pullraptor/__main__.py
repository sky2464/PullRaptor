"""PullRaptor command-line interface entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from pullraptor.kernel import review
from pullraptor.render import render_json, render_markdown, render_sarif


def main(argv: list[str] | None = None) -> int:
    """CLI main function returning process exit code."""
    parser = argparse.ArgumentParser(
        prog="pullraptor",
        description="PullRaptor offline review kernel",
    )
    parser.add_argument("--repo", default=".", help="Path to Git repository root (default: current directory)")
    parser.add_argument("--base", required=True, help="Base Git ref or commit OID")
    parser.add_argument("--head", required=True, help="Head Git ref or commit OID")
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
        report, deadline, record_limits = review(
            repo=repo_path,
            base_ref=args.base,
            head_ref=args.head,
            overrides=overrides,
            started_at=start_monotonic,
            ci=args.ci,
            exact_base=args.exact_base,
            use_cache=not args.no_cache,
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
