"""PullRaptor GitHub PR comment publisher with drift and lifecycle controls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.request

from pullraptor.models import (
    Deadline,
    RecordLimits,
    decode_record,
)

COMMENT_MARKER = "<!-- pullraptor:review -->"


def _github_api_request(
    url: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | list[Any]]:
    """Execute authenticated GitHub REST API request using standard library."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "PullRaptor-Publisher/0.2.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            status = resp.status
            raw_body = resp.read().decode("utf-8")
            body = json.loads(raw_body) if raw_body else {}
            return status, body
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {err.code} on {method} {url}: {err_msg}") from err
    except Exception as err:
        raise RuntimeError(f"GitHub API connection failure on {method} {url}: {err}") from err


def publish_report(
    report_dict: dict[str, Any],
    repo_slug: str,
    pr_number: int,
    token: str,
    *,
    publish_draft: bool = False,
    markdown_override: str | None = None,
    api_base_url: str = "https://api.github.com",
) -> int:
    """Publish a PullRaptor review report to a GitHub pull request.

    Enforces:
    - Bounded report schema validation.
    - Draft PR exclusion unless explicitly enabled.
    - Strict head drift validation (refuses to publish stale review).
    - Idempotent in-place comment update matching COMMENT_MARKER.

    Returns process exit code (0: success, 2: stale/incomplete, 3: error).
    """
    record_limits = RecordLimits()

    try:
        raw_bytes = json.dumps(report_dict).encode("utf-8")
        validated_dict = decode_record(raw_bytes, schema="report", limits=record_limits)
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: invalid report schema: {err}\n")
        return 3

    kind = validated_dict.get("kind")
    if kind == "full":
        contract = validated_dict.get("contract", {})
        reviewed_head = contract.get("head", "")
    elif kind == "limit_failure":
        known_inputs = validated_dict.get("known_inputs", {})
        reviewed_head = str(known_inputs.get("head", ""))
    else:
        sys.stderr.write("PullRaptor Publisher: unrecognized report type\n")
        return 3

    # 1. Fetch current pull request metadata
    pr_url = f"{api_base_url}/repos/{repo_slug}/pulls/{pr_number}"
    _status, pr_data = _github_api_request(pr_url, token)
    if not isinstance(pr_data, dict):
        sys.stderr.write(f"PullRaptor Publisher: invalid PR response for #{pr_number}\n")
        return 3

    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    is_draft = bool(pr_data.get("draft", False))

    # 2. Draft check
    if is_draft and not publish_draft:
        sys.stdout.write(f"PullRaptor Publisher: PR #{pr_number} is a draft; skipping publication\n")
        return 0

    # 3. Head drift check: reject if head has moved
    # Allow prefix match (full SHA vs 12-char or 40-char SHA)
    if reviewed_head and head_sha:
        matches = (
            reviewed_head == head_sha
            or reviewed_head.startswith(head_sha)
            or head_sha.startswith(reviewed_head)
        )
        if not matches:
            sys.stderr.write(
                f"PullRaptor Publisher: STALE_PR_HEAD: Report head {reviewed_head} does not match current PR head {head_sha}. "
                "A newer commit was pushed to this pull request; refusing to post outdated review.\n"
            )
            return 2

    # 4. Render markdown content
    if markdown_override is not None:
        markdown_body = markdown_override
    else:
        lines = ["# PullRaptor Review\n"]
        if kind == "full":
            contract = validated_dict.get("contract", {})
            b_oid = str(contract.get("comparison_base", ""))[:12]
            h_oid = str(contract.get("head", ""))[:12]
            lines.append(f"**Revisions:** Base `{b_oid}` → Head `{h_oid}`")
            lines.append(f"**Profile:** `{contract.get('profile', '')}`\n")
            findings = validated_dict.get("findings", [])
            lines.append("## Findings\n")
            if not findings:
                lines.append("No findings detected. Note: empty findings is not a safety or correctness claim.\n")
            else:
                for f in findings:
                    sp = f.get("span", {})
                    lines.append(f"- **{f.get('rule')}** ({f.get('severity')}): {f.get('claim')} at `{sp.get('path')}:{sp.get('start_line')}`")
        elif kind == "limit_failure":
            lines.append("## Analysis Limit Exceeded\n")
            lines.append(f"- **Cause:** {validated_dict.get('cause')}")
        markdown_body = "\n".join(lines)

    comment_payload = f"{COMMENT_MARKER}\n{markdown_body}"

    # 5. Check for existing PullRaptor comment for idempotency
    comments_url = f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments?per_page=100"
    _c_status, comments_data = _github_api_request(comments_url, token)

    existing_comment_id: int | None = None
    if isinstance(comments_data, list):
        for c in comments_data:
            if isinstance(c, dict) and COMMENT_MARKER in str(c.get("body", "")):
                existing_comment_id = c.get("id")
                break

    # 6. Post or update comment
    if existing_comment_id is not None:
        update_url = f"{api_base_url}/repos/{repo_slug}/issues/comments/{existing_comment_id}"
        _u_status, _ = _github_api_request(update_url, token, method="PATCH", payload={"body": comment_payload})
        sys.stdout.write(f"PullRaptor Publisher: Updated existing review comment {existing_comment_id} on PR #{pr_number}\n")
    else:
        post_url = f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments"
        _p_status, new_comment = _github_api_request(post_url, token, method="POST", payload={"body": comment_payload})
        new_id = new_comment.get("id") if isinstance(new_comment, dict) else "unknown"
        sys.stdout.write(f"PullRaptor Publisher: Published review comment {new_id} on PR #{pr_number}\n")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for pullraptor-publish."""
    parser = argparse.ArgumentParser(
        prog="pullraptor-publish",
        description="Publish PullRaptor review reports to GitHub pull requests",
    )
    parser.add_argument("--report", required=True, help="Path to PullRaptor JSON report file or '-' for stdin")
    parser.add_argument("--repo-slug", required=True, help="GitHub repository slug ('owner/repo')")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--token-env", default="GITHUB_TOKEN", help="Environment variable containing GitHub token (default: GITHUB_TOKEN)")
    parser.add_argument("--publish-draft", action="store_true", help="Publish comments to draft PRs (default: false)")

    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        sys.stderr.write(f"PullRaptor Publisher: Missing GitHub token in environment variable '{args.token_env}'\n")
        return 3

    if args.report == "-":
        raw_report = sys.stdin.read()
    else:
        report_path = Path(args.report).resolve()
        if not report_path.is_file():
            sys.stderr.write(f"PullRaptor Publisher: Report file not found: {report_path}\n")
            return 3
        raw_report = report_path.read_text(encoding="utf-8")

    try:
        report_dict = json.loads(raw_report)
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: Invalid JSON report: {err}\n")
        return 3

    try:
        return publish_report(
            report_dict=report_dict,
            repo_slug=args.repo_slug,
            pr_number=args.pr,
            token=token,
            publish_draft=args.publish_draft,
        )
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: Fatal publication error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
