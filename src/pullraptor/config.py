"""PullRaptor declarative configuration and trusted policy loading."""

from __future__ import annotations

import fnmatch
import math
from dataclasses import fields
from typing import Any
import tomllib

from pullraptor.models import Config

ALLOWED_CONFIG_KEYS = {item.name for item in fields(Config)}


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
        "max_report_bytes", "max_report_items", "max_report_depth", "max_report_string_bytes",
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

    if "source_suffixes" in override_vals and set(base_vals.get("source_suffixes", Config().source_suffixes)) - set(override_vals["source_suffixes"]):
        raise ValueError("CI override cannot weaken required source classification")

    if "path_include" in override_vals:
        base_include = base_vals.get("path_include", ())
        if base_include and set(override_vals["path_include"]) != set(base_include):
            raise ValueError("CI override cannot weaken required scope by modifying path_include")


def _validate_values(values: dict[str, Any]) -> None:
    defaults = Config()
    for name in ALLOWED_CONFIG_KEYS:
        value = values.get(name, getattr(defaults, name))
        if name in {"path_include", "path_exclude", "source_suffixes"}:
            if not isinstance(value, (tuple, list)) or any(not isinstance(item, str) or not item for item in value):
                raise ValueError(f"{name} must be a list of nonempty strings")
        elif name == "profile":
            if value not in {"structural", "diff"}:
                raise ValueError("profile must be structural or diff")
        elif name == "use_cache":
            if type(value) is not bool:
                raise ValueError("use_cache must be boolean")
        elif name == "cache_dir":
            if value is not None and (not isinstance(value, str) or not value or "\x00" in value):
                raise ValueError("cache_dir must be a nonempty path string or null")
        elif name.endswith("seconds"):
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        elif type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    for name, minimum in (("max_report_bytes", 16384), ("max_report_items", 128),
                          ("max_report_depth", 8), ("max_report_string_bytes", 256)):
        if values.get(name, getattr(defaults, name)) < minimum:
            raise ValueError(f"{name} must be >= {minimum} for reserved failure output")


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

        effective_vals.update(overrides)

    _validate_values(effective_vals)
    if ci and overrides:
        _check_ci_weakening(base_vals, overrides)

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
