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
    CoverageReceipt,
    Deadline,
    Diagnostic,
    Finding,
    FullReport,
    LimitFailure,
    RecordLimits,
    Report,
    ReviewContract,
    ScopeEntry,
    Span,
    decode_record,
)
from pullraptor.publication_contract import (
    PublicationContext,
    scope_digest_from_report,
    validate_publication,
)
from pullraptor.publication_lifecycle import PublishedObservation, plan_publication
from pullraptor.render import render_markdown

COMMENT_MARKER = "<!-- pullraptor:review -->"
_BOT_OWNER = "pullraptor-bot"


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


def _span_from_dict(raw: dict[str, Any]) -> Span:
    start_line = int(raw["start_line"])
    return Span(
        path=str(raw["path"]),
        side=str(raw.get("side", "head")),
        start_line=start_line,
        end_line=int(raw.get("end_line", start_line)),
        start_byte=int(raw.get("start_byte", 0)),
        end_byte=int(raw.get("end_byte", 0)),
        start_column=int(raw.get("start_column", 1)),
        end_column=int(raw.get("end_column", 1)),
    )


def _scope_entry_from_dict(raw: dict[str, Any]) -> ScopeEntry:
    path_bytes = raw.get("path_bytes")
    if isinstance(path_bytes, str):
        path_bytes = bytes.fromhex(path_bytes)
    return ScopeEntry(
        key=str(raw["key"]),
        kind=str(raw["kind"]),
        snapshot=str(raw["snapshot"]),
        capability=str(raw["capability"]),
        path_bytes=path_bytes,
        path=raw.get("path"),
        source_occurrence=raw.get("source_occurrence"),
        canonical_target=raw.get("canonical_target"),
        relative_level=raw.get("relative_level"),
        reason=str(raw.get("reason", "")),
    )


def report_from_decoded(validated_dict: dict[str, Any]) -> Report:
    """Materialize a bounded decoded report dict into typed Report records."""
    kind = validated_dict["kind"]
    if kind == "limit_failure":
        return LimitFailure(
            schema=str(validated_dict["schema"]),
            kind=kind,
            known_inputs=dict(validated_dict.get("known_inputs", {})),
            exit_code=int(validated_dict["exit_code"]),
            analysis_complete=bool(validated_dict["analysis_complete"]),
            details_omitted=bool(validated_dict["details_omitted"]),
            cause=str(validated_dict["cause"]),
            limit=validated_dict.get("limit"),
            omitted_domains=tuple(validated_dict.get("omitted_domains", ())),
        )

    contract_raw = validated_dict["contract"]
    contract = ReviewContract(
        base_tip=str(contract_raw["base_tip"]),
        comparison_base=str(contract_raw["comparison_base"]),
        head=str(contract_raw["head"]),
        policy_digest=str(contract_raw["policy_digest"]),
        config_digest=str(contract_raw["config_digest"]),
        tool_digest=str(contract_raw["tool_digest"]),
        profile=str(contract_raw["profile"]),
        expected_scope=tuple(_scope_entry_from_dict(e) for e in contract_raw.get("expected_scope", [])),
        discovery_complete=bool(contract_raw.get("discovery_complete", True)),
    )
    receipts = tuple(
        CoverageReceipt(
            key=str(r["key"]),
            contract_digest=str(r["contract_digest"]),
            capability=str(r["capability"]),
            status=str(r["status"]),
            cause=r.get("cause"),
            recovery=r.get("recovery"),
        )
        for r in validated_dict.get("receipts", [])
    )
    findings = tuple(
        Finding(
            rule=str(f["rule"]),
            version=str(f.get("version", "1")),
            obligation=str(f["obligation"]),
            anchor=str(f["anchor"]),
            span=_span_from_dict(f["span"]),
            claim=str(f["claim"]),
            severity=str(f["severity"]),
            policy_class=str(f["policy_class"]),
            state=str(f["state"]),
            witness=str(f["witness"]),
            assumptions=tuple(f.get("assumptions", ())),
            delta=str(f.get("delta", "newly_detected")),
            evidence_delta=str(f.get("evidence_delta", "added")),
        )
        for f in validated_dict.get("findings", [])
    )
    diagnostics = tuple(
        Diagnostic(
            code=str(d["code"]),
            message=str(d["message"]),
            span=_span_from_dict(d["span"]) if d.get("span") else None,
            path=d.get("path"),
            side=d.get("side"),
            cause=d.get("cause"),
            recovery=d.get("recovery"),
        )
        for d in validated_dict.get("diagnostics", [])
    )
    return FullReport(
        schema=str(validated_dict["schema"]),
        kind=kind,
        contract=contract,
        receipts=receipts,
        inventory=tuple(str(p) for p in validated_dict.get("inventory", ())),
        exclusions=tuple(str(p) for p in validated_dict.get("exclusions", ())),
        findings=findings,
        diagnostics=diagnostics,
        execution=dict(validated_dict.get("execution", {})),
    )


def connector_fields_from_environ() -> dict[str, str]:
    """Read connector-owned publication binding fields from the environment."""
    return {
        "workflow_id": os.environ.get("PULLRAPTOR_WORKFLOW_ID") or os.environ.get("GITHUB_WORKFLOW", ""),
        "run_id": os.environ.get("PULLRAPTOR_RUN_ID") or os.environ.get("GITHUB_RUN_ID", ""),
        "artifact_digest": os.environ.get("PULLRAPTOR_ARTIFACT_DIGEST", ""),
        "reviewer_digest": os.environ.get("PULLRAPTOR_REVIEWER_DIGEST", ""),
        "policy_digest": os.environ.get("PULLRAPTOR_POLICY_DIGEST", ""),
    }


def expected_context_from_report(
    report: FullReport,
    *,
    repository_id: str,
    pr_number: int,
    connector: dict[str, str],
) -> PublicationContext:
    """Build the artifact-pinned expected publication context from the report contract."""
    policy = connector.get("policy_digest") or report.contract.policy_digest
    return PublicationContext(
        repository_id=repository_id,
        pr_number=pr_number,
        workflow_id=connector["workflow_id"],
        run_id=connector["run_id"],
        artifact_digest=connector["artifact_digest"],
        reviewer_digest=connector["reviewer_digest"],
        head=report.contract.head,
        base_tip=report.contract.base_tip,
        comparison_base=report.contract.comparison_base,
        policy_digest=policy,
        scope_digest=scope_digest_from_report(report),
    )


def current_context_from_pr(
    pr_data: dict[str, Any],
    *,
    repository_id: str,
    pr_number: int,
    connector: dict[str, str],
    comparison_base: str,
    base_tip: str,
    scope_digest: str,
    policy_digest: str,
) -> PublicationContext:
    """Build fresh platform context immediately before an authorized write."""
    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    pr_base = str(pr_data.get("base", {}).get("sha", base_tip))
    policy = connector.get("policy_digest") or policy_digest
    return PublicationContext(
        repository_id=repository_id,
        pr_number=pr_number,
        workflow_id=connector["workflow_id"],
        run_id=connector["run_id"],
        artifact_digest=connector["artifact_digest"],
        reviewer_digest=connector["reviewer_digest"],
        head=head_sha,
        base_tip=pr_base,
        comparison_base=comparison_base,
        policy_digest=policy,
        scope_digest=scope_digest,
    )


def observations_from_comments(
    comments: list[Any],
    *,
    bot_owner_id: str = _BOT_OWNER,
) -> tuple[PublishedObservation, ...]:
    """Map connector comment inventory into lifecycle observations (marker comments only)."""
    observations: list[PublishedObservation] = []
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        body = str(entry.get("body", ""))
        if COMMENT_MARKER not in body:
            continue
        user = entry.get("user") if isinstance(entry.get("user"), dict) else {}
        login = str(user.get("login", ""))
        owner_id = bot_owner_id if login.endswith("[bot]") or login == bot_owner_id else login or "unknown"
        platform_id = str(entry.get("id", ""))
        observations.append(
            PublishedObservation(
                owner_id=owner_id,
                platform_id=platform_id,
                obligation_key=COMMENT_MARKER,
                observation_id=platform_id,
                witness_digest="",
                dismissed=False,
            )
        )
    return tuple(observations)


def publish_report(
    report_dict: dict[str, Any],
    repo_slug: str,
    pr_number: int,
    token: str,
    *,
    publish_draft: bool = False,
    markdown_override: str | None = None,
    api_base_url: str = "https://api.github.com",
    preview_only: bool = False,
    expected_context: PublicationContext | None = None,
    connector: dict[str, str] | None = None,
) -> int:
    """Publish a PullRaptor review report to a GitHub pull request.

    Enforces bounded report validation, connector-owned publication binding,
    lifecycle planning, and owned Markdown rendering.

    Returns process exit code (0: success/preview/skip, 2: denied/stale, 3: error).
    """
    record_limits = RecordLimits()
    deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    try:
        raw_bytes = json.dumps(report_dict).encode("utf-8")
        validated_dict = decode_record(raw_bytes, schema="report", limits=record_limits)
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: invalid report schema: {err}\n")
        return 3

    report = report_from_decoded(validated_dict)
    connector_fields = dict(connector or connector_fields_from_environ())

    if isinstance(report, FullReport):
        pinned_expected = expected_context or expected_context_from_report(
            report,
            repository_id=repo_slug,
            pr_number=pr_number,
            connector=connector_fields,
        )
    else:
        pinned_expected = expected_context

    pr_url = f"{api_base_url}/repos/{repo_slug}/pulls/{pr_number}"
    _status, pr_data = _github_api_request(pr_url, token)
    if not isinstance(pr_data, dict):
        sys.stderr.write(f"PullRaptor Publisher: invalid PR response for #{pr_number}\n")
        return 3

    is_draft = bool(pr_data.get("draft", False))
    if is_draft and not publish_draft:
        sys.stdout.write(f"PullRaptor Publisher: PR #{pr_number} is a draft; skipping publication\n")
        return 0

    if pinned_expected is None:
        sys.stderr.write("PullRaptor Publisher: missing publication context for report\n")
        return 3

    scope_digest = pinned_expected.scope_digest
    comparison_base = pinned_expected.comparison_base
    base_tip = pinned_expected.base_tip

    current = current_context_from_pr(
        pr_data,
        repository_id=repo_slug,
        pr_number=pr_number,
        connector=connector_fields,
        comparison_base=comparison_base,
        base_tip=base_tip,
        scope_digest=scope_digest,
        policy_digest=pinned_expected.policy_digest,
    )

    decision = validate_publication(report, pinned_expected, current)
    if not decision.authorized:
        sys.stderr.write(
            f"PullRaptor Publisher: publication denied ({decision.cause}); refusing to post review.\n"
        )
        return 2

    if markdown_override is not None:
        sys.stderr.write(
            "PullRaptor Publisher: markdown override ignored; using owned renderer only.\n"
        )

    markdown_body = render_markdown(report, limits=record_limits, deadline=deadline)
    comment_payload = f"{COMMENT_MARKER}\n{markdown_body}"

    if preview_only:
        sys.stdout.write(f"PullRaptor Publisher: preview only; no comment writes for PR #{pr_number}\n")
        return 0

    comments_url = f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments?per_page=100"
    _c_status, comments_data = _github_api_request(comments_url, token)
    comments_list = comments_data if isinstance(comments_data, list) else []
    existing_observations = observations_from_comments(comments_list)

    artifact_digest = pinned_expected.artifact_digest
    pub_plan = plan_publication(artifact_digest, report, existing_observations)

    _status, pr_data_refresh = _github_api_request(pr_url, token)
    if not isinstance(pr_data_refresh, dict):
        sys.stderr.write(f"PullRaptor Publisher: invalid PR refresh for #{pr_number}\n")
        return 3

    refreshed = current_context_from_pr(
        pr_data_refresh,
        repository_id=repo_slug,
        pr_number=pr_number,
        connector=connector_fields,
        comparison_base=comparison_base,
        base_tip=base_tip,
        scope_digest=scope_digest,
        policy_digest=pinned_expected.policy_digest,
    )
    refresh_decision = validate_publication(report, pinned_expected, refreshed)
    if not refresh_decision.authorized:
        sys.stderr.write(
            f"PullRaptor Publisher: publication denied after refresh ({refresh_decision.cause}); refusing write.\n"
        )
        return 2

    existing_comment_id: int | None = None
    for c in comments_list:
        if isinstance(c, dict) and COMMENT_MARKER in str(c.get("body", "")):
            existing_comment_id = c.get("id")
            break

    should_create = bool(pub_plan.create) or existing_comment_id is None
    if existing_comment_id is not None:
        update_url = f"{api_base_url}/repos/{repo_slug}/issues/comments/{existing_comment_id}"
        _u_status, _ = _github_api_request(update_url, token, method="PATCH", payload={"body": comment_payload})
        sys.stdout.write(
            f"PullRaptor Publisher: Updated existing review comment {existing_comment_id} on PR #{pr_number}\n"
        )
    elif should_create:
        post_url = f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments"
        _p_status, new_comment = _github_api_request(post_url, token, method="POST", payload={"body": comment_payload})
        new_id = new_comment.get("id") if isinstance(new_comment, dict) else "unknown"
        sys.stdout.write(f"PullRaptor Publisher: Published review comment {new_id} on PR #{pr_number}\n")
    else:
        sys.stdout.write(
            f"PullRaptor Publisher: reconciled duplicate delivery; no new comment for PR #{pr_number}\n"
        )

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
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Validate binding and render only; perform no comment writes",
    )

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
            preview_only=args.preview_only,
        )
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: Fatal publication error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
