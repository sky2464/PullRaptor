"""PullRaptor private parser cache."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
from pathlib import Path

from pullraptor.models import ContentFacts, Limits, decode_record, encode_record


def cache_key(
    blob_digest: str,
    runtime: str,
    schema_version: str,
    extractor_digest: str,
) -> str:
    """Compute deterministic cache key from blob digest, runtime, schema, and extractor."""
    content = f"{blob_digest}:{runtime}:{schema_version}:{extractor_digest}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_facts(cache_dir: Path, key: str, limits: Limits) -> ContentFacts | None:
    """Load cached ContentFacts if cache is private, owner-only, and uncorrupted."""
    if not cache_dir.exists() or cache_dir.is_symlink():
        return None

    try:
        st = cache_dir.stat()
        # Verify private directory permissions on POSIX
        if hasattr(os, "getuid"):
            if st.st_uid != os.getuid():
                return None
            if (st.st_mode & 0o077) != 0:
                return None
    except OSError:
        return None

    entry_path = cache_dir / f"{key}.json"
    if not entry_path.exists() or entry_path.is_symlink():
        return None

    try:
        payload = entry_path.read_bytes()
        raw = decode_record(payload, schema="facts", limits=limits.record_limits)

        # Enforce that cached facts never contain occurrence info
        if "path" in raw or "side" in raw or "snapshot" in raw:
            return None

        return ContentFacts(
            blob_digest=raw["blob_digest"],
            runtime_version=raw["runtime_version"],
            schema_version=raw["schema_version"],
            extractor_digest=raw["extractor_digest"],
            symbols=tuple(raw.get("symbols", ())),
            imports=tuple(raw.get("imports", ())),
            pattern_facts=tuple(raw.get("pattern_facts", ())),
            unsupported_constructs=tuple(raw.get("unsupported_constructs", ())),
            relative_locations=tuple(raw.get("relative_locations", ())),
        )
    except Exception:
        return None


def store_facts(cache_dir: Path, key: str, facts: ContentFacts, limits: Limits) -> None:
    """Atomically store ContentFacts into private cache directory."""
    try:
        cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if cache_dir.is_symlink():
            return

        raw = asdict(facts)
        # Ensure no occurrence data is serialized
        for bad_key in ("path", "side", "snapshot"):
            raw.pop(bad_key, None)

        encoded = encode_record(raw, limits.record_limits)
        if len(encoded) > limits.record_limits.max_payload_bytes:
            return

        # Check size cap and evict if needed
        existing = list(cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in existing if f.is_file())
        if total_size + len(encoded) > limits.max_cache_bytes:
            existing.sort(key=lambda f: f.stat().st_mtime)
            while existing and total_size + len(encoded) > limits.max_cache_bytes:
                oldest = existing.pop(0)
                try:
                    sz = oldest.stat().st_size
                    oldest.unlink()
                    total_size -= sz
                except OSError:
                    pass

        tmp_path = cache_dir / f".tmp.{key}.{os.getpid()}"
        tmp_path.write_bytes(encoded)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, cache_dir / f"{key}.json")
    except Exception:
        pass
