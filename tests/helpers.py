"""Test fixtures and git repository helpers for PullRaptor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import tempfile


@dataclass
class FixtureRepo:
    """Temporary git repository for testing."""
    root: Path
    commit_ids: list[str] = field(default_factory=list)

    def commit(self, changes: dict[str, bytes | None], message: str = "commit") -> str:
        for rel_path, content in changes.items():
            full_path = self.root / rel_path
            if content is None:
                if full_path.exists():
                    full_path.unlink()
                subprocess.run(
                    ["git", "rm", "-f", "--ignore-unmatch", rel_path],
                    cwd=self.root,
                    check=True,
                    capture_output=True,
                )
            else:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_bytes(content)
                subprocess.run(
                    ["git", "add", rel_path],
                    cwd=self.root,
                    check=True,
                    capture_output=True,
                )

        res = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        oid = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.commit_ids.append(oid)
        return oid

    def cleanup(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


def make_repo(files: dict[str, bytes]) -> FixtureRepo:
    """Create a temporary git repo initialized with the given files in an initial commit."""
    temp_dir = tempfile.mkdtemp(prefix="pullraptor_test_repo_")
    root = Path(temp_dir)

    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "PullRaptor Tester"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True, capture_output=True)

    repo = FixtureRepo(root=root)
    repo.commit(files, message="initial commit")
    return repo
