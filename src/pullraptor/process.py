"""PullRaptor bounded subprocess execution."""

from __future__ import annotations

import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from pullraptor.models import Deadline, ProcessBounds, ProcessResult


def run_bounded(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    deadline: Deadline,
    bounds: ProcessBounds,
) -> ProcessResult:
    """Run a subprocess with streaming bounded output, isolated environment, and strict deadline.

    Kills the process tree on timeout or output overflow.
    """
    start_time = time.monotonic()
    remaining_deadline = deadline.remaining_work(start_time)
    effective_timeout = min(bounds.timeout_seconds, remaining_deadline)

    if effective_timeout <= 0.0:
        return ProcessResult(
            returncode=-1,
            stdout=b"",
            stderr=b"",
            duration_seconds=0.0,
            timed_out=True,
        )

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
        )
    except Exception as err:
        return ProcessResult(
            returncode=-1,
            stdout=b"",
            stderr=str(err).encode("utf-8"),
            duration_seconds=time.monotonic() - start_time,
            timed_out=False,
        )

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_bytes = 0
    stderr_bytes = 0
    timed_out = False
    stdout_truncated = False
    stderr_truncated = False

    sel = selectors.DefaultSelector()
    if proc.stdout is not None:
        os.set_blocking(proc.stdout.fileno(), False)
        sel.register(proc.stdout, selectors.EVENT_READ, data="stdout")
    if proc.stderr is not None:
        os.set_blocking(proc.stderr.fileno(), False)
        sel.register(proc.stderr, selectors.EVENT_READ, data="stderr")

    def _kill_group() -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    try:
        while sel.get_map():
            now = time.monotonic()
            elapsed = now - start_time
            if elapsed >= effective_timeout or deadline.is_work_exhausted(now):
                timed_out = True
                _kill_group()
                break

            remaining_step = min(effective_timeout - elapsed, 0.1)
            events = sel.select(timeout=max(0.01, remaining_step))

            for key, _mask in events:
                stream_type = key.data
                fileobj = key.fileobj
                try:
                    data = fileobj.read(4096)  # type: ignore
                except Exception:
                    data = b""

                if not data:
                    sel.unregister(fileobj)
                    continue

                if stream_type == "stdout":
                    if stdout_bytes + len(data) > bounds.max_stdout_bytes:
                        allowed = bounds.max_stdout_bytes - stdout_bytes
                        if allowed > 0:
                            stdout_chunks.append(data[:allowed])
                            stdout_bytes += allowed
                        stdout_truncated = True
                        _kill_group()
                        break
                    else:
                        stdout_chunks.append(data)
                        stdout_bytes += len(data)

                elif stream_type == "stderr":
                    if stderr_bytes + len(data) > bounds.max_stderr_bytes:
                        allowed = bounds.max_stderr_bytes - stderr_bytes
                        if allowed > 0:
                            stderr_chunks.append(data[:allowed])
                            stderr_bytes += allowed
                        stderr_truncated = True
                        _kill_group()
                        break
                    else:
                        stderr_chunks.append(data)
                        stderr_bytes += len(data)

            if stdout_truncated or stderr_truncated:
                break

            if proc.poll() is not None and not events:
                break
    finally:
        sel.close()
        if proc.stdout is not None and not proc.stdout.closed:
            try:
                proc.stdout.close()
            except Exception:
                pass
        if proc.stderr is not None and not proc.stderr.closed:
            try:
                proc.stderr.close()
            except Exception:
                pass

    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        _kill_group()
        proc.wait()

    returncode = proc.returncode if proc.returncode is not None else -1
    duration = time.monotonic() - start_time

    return ProcessResult(
        returncode=returncode,
        stdout=b"".join(stdout_chunks),
        stderr=b"".join(stderr_chunks),
        duration_seconds=duration,
        timed_out=timed_out,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )
