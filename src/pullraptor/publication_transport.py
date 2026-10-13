"""Bounded GitHub publication transport with paginated inventory and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

from pullraptor.models import Deadline
from pullraptor.publication_lifecycle import PublicationPlan

RequestFn = Callable[[str, str, str, dict[str, Any] | None], tuple[int, Any]]

MAX_TRANSPORT_ATTEMPTS = 3
MAX_COMMENT_PAGES = 5
COMMENTS_PER_PAGE = 100
_BOT_OWNER = "pullraptor-bot"
COMMENT_MARKER = "<!-- pullraptor:review -->"


class TransportResponseLost(RuntimeError):
    """Raised when a write likely succeeded but the response was not delivered."""


@dataclass(frozen=True)
class PublicationWriteResult:
    """Outcome of one bounded publication write pass."""

    action: str
    comment_id: str | None = None
    cause: str = ""
    attempts: int = 0


def _deadline_remaining(deadline: Deadline) -> float:
    elapsed = time.monotonic() - deadline.started_at
    return max(0.0, deadline.duration_seconds - elapsed)


def _is_rate_limited(status: int, err: BaseException | None = None) -> bool:
    if status in (403, 429):
        return True
    if err is not None:
        text = str(err).lower()
        return "rate limit" in text or "http 403" in text or "http 429" in text
    return False


def fetch_issue_comments_paginated(
    *,
    api_base_url: str,
    repo_slug: str,
    pr_number: int,
    token: str,
    deadline: Deadline,
    request_fn: RequestFn,
    marker: str = COMMENT_MARKER,
) -> tuple[list[dict[str, Any]], str]:
    """Fetch issue comments with bounded pagination; inventory_state is complete or page_cap_truncated."""
    collected: list[dict[str, Any]] = []
    for page in range(1, MAX_COMMENT_PAGES + 1):
        if _deadline_remaining(deadline) <= 0:
            break
        url = (
            f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments"
            f"?per_page={COMMENTS_PER_PAGE}&page={page}"
        )
        try:
            _status, body = request_fn(url, token, "GET", None)
        except RuntimeError:
            break
        if not isinstance(body, list):
            break
        if not body:
            break
        for entry in body:
            if isinstance(entry, dict):
                collected.append(entry)
        if len(body) < COMMENTS_PER_PAGE:
            return collected, "complete"
    if len(collected) >= MAX_COMMENT_PAGES * COMMENTS_PER_PAGE:
        return collected, "page_cap_truncated"
    if _deadline_remaining(deadline) <= 0:
        return collected, "deadline_exceeded"
    return collected, "complete"


def find_owned_review_comment_id(
    comments: list[Any],
    *,
    bot_owner_id: str = _BOT_OWNER,
    marker: str = COMMENT_MARKER,
) -> int | None:
    """Return platform comment ID for bot-owned marker comment, ignoring foreign markers."""
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        body = str(entry.get("body", ""))
        if marker not in body:
            continue
        user = entry.get("user") if isinstance(entry.get("user"), dict) else {}
        login = str(user.get("login", ""))
        if login.endswith("[bot]") or login == bot_owner_id:
            comment_id = entry.get("id")
            if comment_id is not None:
                return int(comment_id)
    return None


def apply_publication_write(
    *,
    api_base_url: str,
    repo_slug: str,
    pr_number: int,
    token: str,
    comment_payload: str,
    pub_plan: PublicationPlan,
    owned_comment_id: int | None,
    deadline: Deadline,
    request_fn: RequestFn,
    marker: str = COMMENT_MARKER,
    before_write: Callable[[], str | None] | None = None,
) -> PublicationWriteResult:
    """Execute create/update with bounded retries and lost-response reconciliation."""
    should_create = bool(pub_plan.create) or owned_comment_id is None

    if before_write is None:
        return PublicationWriteResult(action="denied", cause="missing_publication_authority")

    attempts = 0
    last_err: BaseException | None = None
    while attempts < MAX_TRANSPORT_ATTEMPTS and _deadline_remaining(deadline) > 0:
        try:
            denial = before_write()
        except Exception:
            denial = "current_authority_unavailable"
        if denial is not None:
            return PublicationWriteResult(action="denied", cause=denial, attempts=attempts)
        if _deadline_remaining(deadline) <= 0:
            break
        attempts += 1
        try:
            if owned_comment_id is not None:
                url = f"{api_base_url}/repos/{repo_slug}/issues/comments/{owned_comment_id}"
                status, body = request_fn(url, token, "PATCH", {"body": comment_payload})
                if _is_rate_limited(status):
                    return PublicationWriteResult(
                        action="deferred",
                        comment_id=str(owned_comment_id),
                        cause="rate_limited",
                        attempts=attempts,
                    )
                return PublicationWriteResult(
                    action="updated",
                    comment_id=str(owned_comment_id),
                    attempts=attempts,
                )

            post_url = f"{api_base_url}/repos/{repo_slug}/issues/{pr_number}/comments"
            status, body = request_fn(post_url, token, "POST", {"body": comment_payload})
            if _is_rate_limited(status):
                return PublicationWriteResult(action="deferred", cause="rate_limited", attempts=attempts)
            new_id = body.get("id") if isinstance(body, dict) else None
            return PublicationWriteResult(
                action="created",
                comment_id=str(new_id) if new_id is not None else None,
                attempts=attempts,
            )
        except TransportResponseLost as err:
            last_err = err
            comments, _state = fetch_issue_comments_paginated(
                api_base_url=api_base_url,
                repo_slug=repo_slug,
                pr_number=pr_number,
                token=token,
                deadline=deadline,
                request_fn=request_fn,
                marker=marker,
            )
            reconciled_id = find_owned_review_comment_id(comments, marker=marker)
            if reconciled_id is not None:
                return PublicationWriteResult(
                    action="reconciled",
                    comment_id=str(reconciled_id),
                    cause="lost_response",
                    attempts=attempts,
                )
            owned_comment_id = reconciled_id
            continue
        except RuntimeError as err:
            last_err = err
            if _is_rate_limited(0, err):
                return PublicationWriteResult(action="deferred", cause="rate_limited", attempts=attempts)
            comments, _state = fetch_issue_comments_paginated(
                api_base_url=api_base_url,
                repo_slug=repo_slug,
                pr_number=pr_number,
                token=token,
                deadline=deadline,
                request_fn=request_fn,
                marker=marker,
            )
            reconciled_id = find_owned_review_comment_id(comments, marker=marker)
            if reconciled_id is not None:
                return PublicationWriteResult(
                    action="reconciled",
                    comment_id=str(reconciled_id),
                    cause="ambiguous_write",
                    attempts=attempts,
                )
            continue

    if owned_comment_id is not None and not should_create:
        return PublicationWriteResult(
            action="reconciled",
            comment_id=str(owned_comment_id),
            cause="duplicate_delivery",
            attempts=attempts,
        )

    cause = "deadline_exceeded" if _deadline_remaining(deadline) <= 0 else "transport_failed"
    if last_err is not None and cause == "transport_failed":
        cause = str(last_err)[:120]
    return PublicationWriteResult(action="error", cause=cause, attempts=attempts)
