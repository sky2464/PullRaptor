"""PullRaptor declarative configuration and trusted policy loading."""

from __future__ import annotations

import fnmatch
from typing import Any
import tomllib

from pullraptor.models import Config

ALLOWED_CONFIG_KEYS = {
    "profile",
    "max_tracked_entries",
    "max_blob_bytes",
    "max_total_bytes",
    "parse_timeout_seconds",
    "review_timeout_seconds",
    "failure_reserve_seconds",
    "path_include",
    "path_exclude",
    "source_suffixes",
    "use_cache",
    "cache_dir",
    "max_cache_bytes",
}


def matches_path(path: str, patterns: tuple[str, ...]) -> bool:
    """Check whether a repository-relative path matches any of the glob patterns.

    Separators normalize to '/'. Matches use case-sensitive fnmatchcase.
    """
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pat) for pat in patterns)


def _check_ci_weakening(base_vals: dict[str, Any], override_vals: dict[str, Any]) -> None:
    """Ensure CI overrides cannot weaken analysis scope or safety thresholds."""
    if "profile" in override_vals:
        if base_vals.get("profile", "structural") == "structural" and override_vals["profile"] == "diff":
            raise ValueError("CI override cannot weaken required scope: profile cannot be downgraded to 'diff'")

    numeric_thresholds = [
        "max_tracked_entries",
        "max_blob_bytes",
        "max_total_bytes",
        "review_timeout_seconds",
        "parse_timeout_seconds",
    ]
    for key in numeric_thresholds:
        if key in override_vals:
            base_val = base_vals.get(key, getattr(Config(), key))
            if override_vals[key] < base_val:
                raise ValueError(
                    f"CI override cannot weaken threshold for {key}: {override_vals[key]} < {base_val}"
                )

    if "path_exclude" in override_vals and override_vals["path_exclude"]:
        base_exclude = set(base_vals.get("path_exclude", ()))
        override_exclude = set(override_vals["path_exclude"])
        if not override_exclude.issubset(base_exclude):
            raise ValueError("CI override cannot weaken required scope by adding path exclusions")

    if "path_include" in override_vals:
        base_include = base_vals.get("path_include", ())
        if base_include and set(override_vals["path_include"]) != set(base_include):
            raise ValueError("CI override cannot weaken required scope by modifying path_include")


def load_config(
    policy_bytes: bytes | None,
    overrides: dict[str, Any] | None = None,
    *,
    ci: bool = False,
) -> Config:
    """Load configuration from trusted base policy TOML bytes and optional overrides.

    Unknown keys are errors. Enforces minimum finalization capacity and prevents
    weakening in CI environments.
    """
    base_vals: dict[str, Any] = {}

    if policy_bytes is not None:
        try:
            parsed = tomllib.loads(policy_bytes.decode("utf-8"))
        except Exception as err:
            raise ValueError(f"Failed to parse policy TOML: {err}") from err

        for k, v in parsed.items():
            if k not in ALLOWED_CONFIG_KEYS:
                raise ValueError(f"Unknown configuration key in policy: {k!r}")
            base_vals[k] = v

    effective_vals = dict(base_vals)

    if overrides is not None:
        for k, v in overrides.items():
            if k not in ALLOWED_CONFIG_KEYS:
                raise ValueError(f"Unknown configuration key in override: {k!r}")

        if ci:
            _check_ci_weakening(base_vals, overrides)

        effective_vals.update(overrides)

    # Convert list values to immutable tuples
    for list_key in ("path_include", "path_exclude", "source_suffixes"):
        if list_key in effective_vals:
            effective_vals[list_key] = tuple(effective_vals[list_key])

    # Validate review timeout and reserve
    default_cfg = Config()
    review_timeout = effective_vals.get("review_timeout_seconds", default_cfg.review_timeout_seconds)
    failure_reserve = effective_vals.get("failure_reserve_seconds", default_cfg.failure_reserve_seconds)

    if review_timeout < 3.0:
        raise ValueError(
            f"review_timeout_seconds must be >= 3.0 to reserve finalization capacity, got {review_timeout}"
        )
    if failure_reserve < 0.0 or review_timeout <= failure_reserve:
        raise ValueError(
            f"failure_reserve_seconds ({failure_reserve}) must be positive and less than review_timeout_seconds ({review_timeout})"
        )

    return Config(**effective_vals)
