"""Descriptor-bound private parser cache; unavailable controls disable caching."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from pullraptor.models import ContentFacts, Limits, decode_record, encode_record
from pullraptor.python_facts import content_record

_KEY = re.compile(r"[0-9a-f]{64}\Z")
MAX_CACHE_ENTRIES = 10_000


def cache_key(blob_digest: str, runtime: str, schema_version: str, extractor_digest: str) -> str:
    """Versioned, unambiguous identity for occurrence-free content facts."""
    raw = json.dumps(['pullraptor.cache-key/2', blob_digest, runtime, schema_version,
                      extractor_digest], separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _valid_key(key: str) -> bool:
    return isinstance(key, str) and _KEY.fullmatch(key) is not None


def _directory(st: os.stat_result, *, private: bool) -> bool:
    if not stat.S_ISDIR(st.st_mode):
        return False
    if private:
        return st.st_uid == os.getuid() and not st.st_mode & 0o077
    # Root/caller-owned ancestors cannot be writable by other users. Root-owned
    # sticky temporary roots are admitted; every component is still no-follow.
    return st.st_uid in (0, os.getuid()) and (
        not st.st_mode & 0o022 or (st.st_uid == 0 and bool(st.st_mode & stat.S_ISVTX)))


def _open_cache(cache_dir: Path, *, create: bool) -> int | None:
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        return None
    raw_path = os.fspath(cache_dir)
    if '..' in Path(raw_path).parts:
        return None
    parts = Path(os.path.abspath(raw_path)).parts[1:]
    if not parts:
        return None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = None
    try:
        fd = os.open('/', flags)
        for index, part in enumerate(parts):
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=fd)
                next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if not _directory(os.fstat(fd), private=index == len(parts)-1):
                raise OSError('untrusted cache directory')
        return fd
    except (OSError, ValueError, TypeError, NotImplementedError):
        if fd is not None:
            os.close(fd)
        return None


def _private_entry(st: os.stat_result) -> bool:
    return (stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid()
            and not st.st_mode & 0o077 and st.st_nlink == 1)


def _identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink,
            st.st_uid, st.st_mode)


def load_facts(cache_dir: Path, key: str, limits: Limits) -> ContentFacts | None:
    """Bounded no-follow read; validate private provenance, facts and requested identity."""
    if not _valid_key(key):
        return None
    directory_fd = _open_cache(cache_dir, create=False)
    if directory_fd is None:
        return None
    entry_fd = None
    try:
        entry_fd = os.open(key + '.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                           | os.O_NONBLOCK, dir_fd=directory_fd)
        before = os.fstat(entry_fd)
        cap = min(limits.record_limits.max_payload_bytes, limits.max_cache_bytes)
        if not _private_entry(before) or before.st_size > cap or cap < 1:
            return None
        payload = bytearray()
        while len(payload) <= cap:
            chunk = os.read(entry_fd, min(65_536, cap + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > cap or _identity(os.fstat(entry_fd)) != _identity(before):
            return None
        if not _directory(os.fstat(directory_fd), private=True):
            return None
        facts = content_record(decode_record(bytes(payload), schema='facts', limits=limits.record_limits))
        expected = cache_key(facts.blob_digest, facts.runtime_version, facts.schema_version,
                             facts.extractor_digest)
        return facts if expected == key else None
    except (OSError, ValueError, TypeError, KeyError, NotImplementedError):
        return None
    finally:
        if entry_fd is not None:
            os.close(entry_fd)
        os.close(directory_fd)


def _scan(directory_fd: int, max_entries: int) -> list[tuple[str, os.stat_result]] | None:
    """Bound entry enumeration and admit no foreign/shared/link entries."""
    entries = []
    with os.scandir(directory_fd) as listing:
        for entry in listing:
            if len(entries) >= max_entries:
                return None
            info = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
            if not _private_entry(info):
                return None
            # Unknown files are never evicted, but count toward all bounds.
            entries.append((entry.name, info))
    return entries


def store_facts(cache_dir: Path, key: str, facts: ContentFacts, limits: Limits) -> None:
    """Validate identity, then O_EXCL/0600/fsync/replace within an admitted dirfd."""
    if not _valid_key(key):
        return
    try:
        encoded = encode_record(asdict(facts), limits.record_limits)
        strict = content_record(decode_record(encoded, schema='facts', limits=limits.record_limits))
        if cache_key(strict.blob_digest, strict.runtime_version, strict.schema_version,
                     strict.extractor_digest) != key or len(encoded) > limits.max_cache_bytes:
            return
    except (ValueError, TypeError, KeyError):
        return
    directory_fd = _open_cache(cache_dir, create=True)
    if directory_fd is None:
        return
    temporary = None
    temp_fd = None
    try:
        entry_cap = min(MAX_CACHE_ENTRIES, limits.max_tracked_entries)
        entries = _scan(directory_fd, entry_cap)
        if entries is None:
            return
        target = key + '.json'
        old = next((info for name, info in entries if name == target), None)
        total = sum(info.st_size for _, info in entries)
        entry_count = len(entries)
        # Bound peak storage too: retain the old entry until atomic replacement.
        for name, info in sorted(entries, key=lambda item: (item[1].st_mtime_ns, item[0])):
            if total + len(encoded) <= limits.max_cache_bytes and entry_count + 1 <= entry_cap:
                break
            if name == target or not name.endswith('.json') or not _valid_key(name[:-5]):
                continue
            if _identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)) != _identity(info):
                return
            os.unlink(name, dir_fd=directory_fd)
            total -= info.st_size
            entry_count -= 1
        if total + len(encoded) > limits.max_cache_bytes or entry_count + 1 > entry_cap:
            return
        for _ in range(8):
            temporary = '.tmp.' + secrets.token_hex(16)
            try:
                temp_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                  | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
                break
            except FileExistsError:
                temporary = None
        if temp_fd is None:
            return
        offset = 0
        while offset < len(encoded):
            count = os.write(temp_fd, encoded[offset:])
            if count <= 0:
                raise OSError('short cache write')
            offset += count
        os.fsync(temp_fd)
        temp_info = os.fstat(temp_fd)
        if not _private_entry(temp_info) or not _directory(os.fstat(directory_fd), private=True):
            return
        if _identity(os.stat(temporary, dir_fd=directory_fd, follow_symlinks=False)) != _identity(temp_info):
            return
        try:
            current = os.stat(target, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if (old is None) != (current is None) or (old is not None and _identity(old) != _identity(current)):
            return
        os.replace(temporary, target, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        temporary = None
        os.fsync(directory_fd)
    except (OSError, ValueError, TypeError, NotImplementedError):
        return
    finally:
        if temp_fd is not None:
            os.close(temp_fd)
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass
        os.close(directory_fd)
