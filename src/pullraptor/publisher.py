"""PullRaptor GitHub PR comment publisher with drift and lifecycle controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request

from pullraptor.beta_admission import admit_console_script
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
    PublicationDecision,
    validate_publication,
)
from pullraptor.publication_lifecycle import PublishedObservation, plan_publication
from pullraptor.publication_transport import (
    COMMENT_MARKER,
    apply_publication_write,
    fetch_issue_comments_paginated,
    find_owned_review_comment_id,
)
from pullraptor.render import render_markdown
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
    start_line = raw["start_line"]
    return Span(
        path=raw["path"],
        side=raw["side"],
        start_line=start_line,
        end_line=raw["end_line"],
        start_byte=raw.get("start_byte", 0),
        end_byte=raw.get("end_byte", 0),
        start_column=raw.get("start_column", 1),
        end_column=raw.get("end_column", 1),
    )


def _scope_entry_from_dict(raw: dict[str, Any]) -> ScopeEntry:
    path_bytes = raw.get("path_bytes")
    if isinstance(path_bytes, str):
        path_bytes = bytes.fromhex(path_bytes)
    return ScopeEntry(
        key=raw["key"],
        kind=raw["kind"],
        snapshot=raw["snapshot"],
        capability=raw["capability"],
        path_bytes=path_bytes,
        path=raw.get("path"),
        source_occurrence=raw.get("source_occurrence"),
        canonical_target=raw.get("canonical_target"),
        relative_level=raw.get("relative_level"),
        reason=raw.get("reason", ""),
    )


def report_from_decoded(validated_dict: dict[str, Any]) -> Report:
    """Materialize a bounded decoded report dict into typed Report records."""
    kind = validated_dict["kind"]
    if kind == "limit_failure":
        return LimitFailure(
            schema=validated_dict["schema"],
            kind=kind,
            known_inputs=dict(validated_dict.get("known_inputs", {})),
            exit_code=validated_dict["exit_code"],
            analysis_complete=validated_dict["analysis_complete"],
            details_omitted=validated_dict["details_omitted"],
            cause=validated_dict["cause"],
            limit=validated_dict.get("limit"),
            omitted_domains=tuple(validated_dict.get("omitted_domains", ())),
        )

    contract_raw = validated_dict["contract"]
    if type(contract_raw.get("discovery_complete")) is not bool:
        raise ValueError("discovery_complete must be a boolean")
    for field in ("base_tip", "comparison_base", "head", "policy_digest", "config_digest", "tool_digest", "profile"):
        if type(contract_raw[field]) is not str:
            raise ValueError(f"contract {field} must be a string")
    contract = ReviewContract(
        base_tip=contract_raw["base_tip"],
        comparison_base=contract_raw["comparison_base"],
        head=contract_raw["head"],
        policy_digest=contract_raw["policy_digest"],
        config_digest=contract_raw["config_digest"],
        tool_digest=contract_raw["tool_digest"],
        profile=contract_raw["profile"],
        expected_scope=tuple(_scope_entry_from_dict(e) for e in contract_raw["expected_scope"]),
        discovery_complete=contract_raw["discovery_complete"],
    )
    receipts = tuple(
        CoverageReceipt(
            key=r["key"],
            contract_digest=r["contract_digest"],
            capability=r["capability"],
            status=r["status"],
            cause=r.get("cause"),
            recovery=r.get("recovery"),
        )
        for r in validated_dict.get("receipts", [])
    )
    findings = tuple(
        Finding(
            rule=f["rule"],
            version=f.get("version", "1"),
            obligation=f["obligation"],
            anchor=f["anchor"],
            span=_span_from_dict(f["span"]),
            claim=f["claim"],
            severity=f["severity"],
            policy_class=f["policy_class"],
            state=f["state"],
            witness=f["witness"],
            assumptions=tuple(f.get("assumptions", ())),
            delta=f.get("delta", "newly_detected"),
            evidence_delta=f.get("evidence_delta", "added"),
        )
        for f in validated_dict.get("findings", [])
    )
    diagnostics = tuple(
        Diagnostic(
            code=d["code"],
            message=d["message"],
            span=_span_from_dict(d["span"]) if d.get("span") else None,
            path=d.get("path"),
            side=d.get("side"),
            cause=d.get("cause"),
            recovery=d.get("recovery"),
        )
        for d in validated_dict.get("diagnostics", [])
    )
    return FullReport(
        schema=validated_dict["schema"],
        kind=kind,
        contract=contract,
        receipts=receipts,
        inventory=tuple(str(p) for p in validated_dict.get("inventory", ())),
        exclusions=tuple(str(p) for p in validated_dict.get("exclusions", ())),
        findings=findings,
        diagnostics=diagnostics,
        execution=dict(validated_dict.get("execution", {})),
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
    raw_report_bytes: bytes | None = None,
    current_authority: Callable[[dict[str, Any]], PublicationContext] | None = None,
) -> int:
    """Publish a PullRaptor review report to a GitHub pull request.

    Enforces bounded report validation, connector-owned publication binding,
    lifecycle planning, and owned Markdown rendering. expected_context is a
    trusted frozen connector authority; current_authority re-derives all fields
    from current connector metadata and trusted policy before each write/retry.
    raw_report_bytes are the exact downloaded bytes. The legacy connector mapping
    is inert and cannot grant authorization.

    Returns process exit code (0: success/preview/skip, 2: denied/stale, 3: error).
    """
    record_limits = RecordLimits()
    deadline = Deadline(started_at=time.monotonic(), duration_seconds=30.0)

    if not isinstance(expected_context, PublicationContext) or not callable(current_authority):
        sys.stderr.write("PullRaptor Publisher: missing_publication_authority; refusing write.\n")
        return 2
    if not isinstance(raw_report_bytes, bytes):
        sys.stderr.write("PullRaptor Publisher: missing_report_bytes; refusing write.\n")
        return 2
    try:
        validated_dict = decode_record(raw_report_bytes, schema="report", limits=record_limits)
        if validated_dict != report_dict:
            sys.stderr.write("PullRaptor Publisher: report_bytes_mismatch; refusing write.\n")
            return 2
        report = report_from_decoded(validated_dict)
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: invalid report schema: {err}\n")
        return 3
    pinned_expected = expected_context
    if (pinned_expected.repository_id != repo_slug or pinned_expected.pr_number != pr_number):
        sys.stderr.write("PullRaptor Publisher: request_context_mismatch; refusing write.\n")
        return 2
    actual_digest = hashlib.sha256(raw_report_bytes).hexdigest()

    pr_url = f"{api_base_url}/repos/{repo_slug}/pulls/{pr_number}"
    _status, pr_data = _github_api_request(pr_url, token)
    if not isinstance(pr_data, dict):
        sys.stderr.write(f"PullRaptor Publisher: invalid PR response for #{pr_number}\n")
        return 3

    is_draft = bool(pr_data.get("draft", False))
    if is_draft and not publish_draft:
        sys.stdout.write(f"PullRaptor Publisher: PR #{pr_number} is a draft; skipping publication\n")
        return 0

    def authorize(pr: dict[str, Any]) -> PublicationDecision:
        # The callback is trusted connector code, refreshing origin/contract/diff
        # authority independently. Neither a report envelope nor environment
        # strings can substitute for it.
        try:
            current = current_authority(pr)
            if not isinstance(current, PublicationContext):
                raise ValueError("missing_publication_authority")
            if (current.head != pr.get("head", {}).get("sha")
                    or current.base_tip != pr.get("base", {}).get("sha")):
                raise ValueError("platform_context_mismatch")
            return validate_publication(report, pinned_expected, current,
                                        actual_report_digest=actual_digest)
        except Exception:
            return PublicationDecision(False, "current_authority_unavailable", ())

    decision = authorize(pr_data)
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

    def _transport_request(
        url: str,
        auth_token: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        status, body = _github_api_request(url, auth_token, method=method, payload=payload)
        return status, body

    comments_list, _inventory_state = fetch_issue_comments_paginated(
        api_base_url=api_base_url,
        repo_slug=repo_slug,
        pr_number=pr_number,
        token=token,
        deadline=deadline,
        request_fn=_transport_request,
    )
    existing_observations = observations_from_comments(comments_list)

    artifact_digest = pinned_expected.artifact_digest
    pub_plan = plan_publication(artifact_digest, report, existing_observations)

    def before_write() -> str | None:
        try:
            _status, fresh_pr = _github_api_request(pr_url, token)
            if not isinstance(fresh_pr, dict):
                return "invalid_pr_refresh"
            if fresh_pr.get("draft", False) and not publish_draft:
                return "draft_pr"
            fresh_decision = authorize(fresh_pr)
            return None if fresh_decision.authorized else fresh_decision.cause
        except Exception:
            return "current_authority_unavailable"

    owned_comment_id = find_owned_review_comment_id(comments_list)

    write_result = apply_publication_write(
        api_base_url=api_base_url,
        repo_slug=repo_slug,
        pr_number=pr_number,
        token=token,
        comment_payload=comment_payload,
        pub_plan=pub_plan,
        owned_comment_id=owned_comment_id,
        deadline=deadline,
        request_fn=_transport_request,
        before_write=before_write,
    )

    if write_result.action == "denied":
        sys.stderr.write(f"PullRaptor Publisher: publication denied ({write_result.cause}); refusing write.\n")
        return 2
    if write_result.action == "created":
        sys.stdout.write(
            f"PullRaptor Publisher: Published review comment {write_result.comment_id} on PR #{pr_number}\n"
        )
    elif write_result.action == "updated":
        sys.stdout.write(
            f"PullRaptor Publisher: Updated existing review comment {write_result.comment_id} on PR #{pr_number}\n"
        )
    elif write_result.action == "reconciled":
        sys.stdout.write(
            f"PullRaptor Publisher: reconciled duplicate delivery; no new comment for PR #{pr_number}\n"
        )
    elif write_result.action == "deferred":
        sys.stdout.write(
            f"PullRaptor Publisher: deferred publication ({write_result.cause}) for PR #{pr_number}\n"
        )
    else:
        sys.stderr.write(
            f"PullRaptor Publisher: publication transport failed ({write_result.cause}) for PR #{pr_number}\n"
        )
        return 3

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for pullraptor-publish."""
    admitted, message = admit_console_script("pullraptor-publish")
    if not admitted:
        sys.stderr.write(message + "\n")
        return 2
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
        raw_report_bytes = sys.stdin.buffer.read()
    else:
        report_path = Path(args.report).resolve()
        if not report_path.is_file():
            sys.stderr.write(f"PullRaptor Publisher: Report file not found: {report_path}\n")
            return 3
        raw_report_bytes = report_path.read_bytes()

    try:
        report_dict = json.loads(raw_report_bytes)
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
            raw_report_bytes=raw_report_bytes,
        )
    except Exception as err:
        sys.stderr.write(f"PullRaptor Publisher: Fatal publication error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
