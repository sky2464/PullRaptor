"""Beta 0.1.x distribution admission gates (implementer-collected; not independent acceptance)."""

from __future__ import annotations

import os

BETA_HUMAN_LABEL = "0.1.x"
_DEV_OVERRIDE_ENV = "PULLRAPTOR_DEV_ADMIT_EXTENDED"

_INCLUDED_CONSOLE_SCRIPTS = frozenset({"pullraptor"})


def dev_override_enabled() -> bool:
    value = os.environ.get(_DEV_OVERRIDE_ENV, "").strip().lower()
    return value in {"1", "true", "yes"}


def admit_console_script(command: str) -> tuple[bool, str]:
    """Return (admitted, refusal_message). Included beta console scripts pass without override."""
    if command in _INCLUDED_CONSOLE_SCRIPTS or dev_override_enabled():
        return True, ""
    return False, (
        f"PullRaptor beta {BETA_HUMAN_LABEL} excludes console script '{command}'. "
        "See docs/releases/beta-0.1-scope.json. "
        f"Development-only override: {_DEV_OVERRIDE_ENV}=1."
    )


def admit_cli_review_flags(
    *,
    staged: bool,
    workdir: bool,
    include_untracked: bool,
    mcp: bool,
    ai_endpoint: str | None,
) -> tuple[bool, str]:
    if dev_override_enabled():
        return True, ""
    if mcp:
        return False, (
            f"PullRaptor beta {BETA_HUMAN_LABEL} excludes MCP on the review CLI. "
            "Use the included offline `pullraptor --head` flow or admit extended interfaces via "
            f"{_DEV_OVERRIDE_ENV}=1 for development."
        )
    if staged or workdir or include_untracked:
        return False, (
            f"PullRaptor beta {BETA_HUMAN_LABEL} excludes local snapshot review "
            "(--staged/--workdir/--include-untracked). Exact Git revision review with --head is included; "
            "local snapshots require E02-A1 evidence. "
            f"Development override: {_DEV_OVERRIDE_ENV}=1."
        )
    if ai_endpoint:
        return False, (
            f"PullRaptor beta {BETA_HUMAN_LABEL} excludes optional AI network transport. "
            f"Development override: {_DEV_OVERRIDE_ENV}=1."
        )
    return True, ""
