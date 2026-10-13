"""Trusted BR18 test helper: pause actual pinned pip filesystem operations.

Never installed in the customer artifact. Only the disposable venv's installer is
instrumented; original pip removal/write functions perform all mutations.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import sys


def main():
    if importlib.metadata.version("pip") != "26.2.1":
        raise RuntimeError("reviewed installer pip==26.2.1 required")
    from pip._internal.cli.main import main as pip_main
    from pip._internal.req.req_uninstall import UninstallPathSet
    from pip._internal.operations.install.wheel import ZipBackedFile
    event_path, checkpoint, site = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]).resolve()
    original_remove = UninstallPathSet.remove
    original_save = ZipBackedFile.save
    identities = {
        "remove_function_sha256": hashlib.sha256(inspect.getsource(original_remove).encode()).hexdigest(),
        "save_function_sha256": hashlib.sha256(inspect.getsource(original_save).encode()).hexdigest(),
    }

    expected = {"remove_function_sha256": "106b3b3e9c137dd5b31055522f9d33669239fef07fa965ad1814e82ff135e66c",
                "save_function_sha256": "27ef5509c37567790cbee991830013e1cb2c77cf01649605b0fb7c398efabc76"}
    if identities != expected:
        raise RuntimeError("reviewed pip filesystem function identity mismatch")

    def reached(name, written=None):
        if checkpoint != name:
            return
        old = site / "pullraptor-0.1.0b1.dist-info"
        new = site / "pullraptor-0.1.0b2.dev0.dist-info"
        files = sorted(str(p.relative_to(site)) for p in (site / "pullraptor").rglob("*") if p.is_file())
        if old.exists() or new.exists() or len(files) != (0 if written is None else 1):
            raise RuntimeError("installer checkpoint did not reach required filesystem state")
        payload = {"name": name, "reached": True, "pid": os.getpid(), "written": written,
                   "package_files": files, **identities}
        with event_path.open("w") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        # Parent holds stdin open and kills the whole process group after it has
        # inspected the checkpoint. No delay predicts the installer's progress.
        os.read(0, 1)
        raise RuntimeError("checkpoint released without assigned interruption")

    def remove(self, *args, **kwargs):
        result = original_remove(self, *args, **kwargs)
        if self._dist.raw_name == "pullraptor" and str(self._dist.raw_version) == "0.1.0b1":
            reached("after_old_dist_info_removal")
        return result

    package_writes = 0

    def save(self, *args, **kwargs):
        nonlocal package_writes
        result = original_save(self, *args, **kwargs)
        dest = Path(self.dest_path).resolve()
        if dest.is_relative_to(site / "pullraptor"):
            package_writes += 1
            if package_writes == 1:
                reached("after_first_package_write", str(dest.relative_to(site)))
        return result

    UninstallPathSet.remove = remove
    ZipBackedFile.save = save
    return pip_main(sys.argv[4:])


if __name__ == "__main__":
    sys.exit(main())
