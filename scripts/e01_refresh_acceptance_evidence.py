#!/usr/bin/env python3.12
"""Refresh E01 boundary/cache/corpus acceptance artifact indexes (development verification)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ART = REPO / "docs" / "acceptance" / "artifacts" / "E01"


def _rev() -> str:
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def _run_tests(modules: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", *modules, "-v"],
        cwd=REPO,
        env={**dict(__import__("os").environ), "PYTHONPATH": f"{REPO / 'src'}{__import__('os').pathsep}{REPO}"},
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    rev = _rev()
    boundary_code, boundary_log = _run_tests(
        ["tests.test_e01_offline_boundaries", "tests.test_cli", "tests.test_render"],
    )
    cache_code, cache_log = _run_tests(["tests.test_cache", "tests.test_kernel"])
    corpus_code, corpus_log = _run_tests(["tests.test_rules"])

    boundary_log_path = ART / "boundaries" / "focused-boundary.log"
    boundary_log_path.write_text(boundary_log, encoding="utf-8")
    cache_log_path = ART / "cache" / "focused-cache.log"
    cache_log_path.write_text(cache_log, encoding="utf-8")
    corpus_log_path = ART / "corpus" / "focused-corpus.log"
    corpus_log_path.write_text(corpus_log, encoding="utf-8")

    if boundary_code == 0:
        receipt_path = ART / "boundaries" / "offline-network-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "schema": "pullraptor-e01-boundary-receipt/1",
                    "check": "offline_review_no_socket",
                    "tests": ["tests/test_e01_offline_boundaries.py"],
                    "source_revision": rev,
                    "result": "passed",
                    "note": "Development verification; independent BR-03 acceptance remains separate.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    (ART / "boundaries" / "index.json").write_text(
        json.dumps(
            {
                "card_id": "E01-T9-RECORDS",
                "source_revision": rev,
                "evidence_status": "development_passed" if boundary_code == 0 else "failed",
                "offline_network_receipt": "docs/acceptance/artifacts/E01/boundaries/offline-network-receipt.json",
                "focused_log": str(boundary_log_path.relative_to(REPO)),
                "independent_acceptance": "pending_BR-07",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    cache_fixture = REPO / "tests" / "fixtures" / "e01" / "cache-mutations" / "manifest.json"
    cache_fixture.parent.mkdir(parents=True, exist_ok=True)
    cache_fixture.write_text(
        json.dumps(
            {
                "schema": "pullraptor-e01-cache-fixtures/1",
                "source_revision": rev,
                "coverage": "tests/test_cache.py mutation and trust cases",
                "status": "mapped_to_unittests",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (ART / "cache" / "index.json").write_text(
        json.dumps(
            {
                "card_id": "E01-T9-CACHE",
                "source_revision": rev,
                "evidence_status": "development_passed" if cache_code == 0 else "failed",
                "fixture_directory": "tests/fixtures/e01/cache-mutations",
                "focused_log": str(cache_log_path.relative_to(REPO)),
                "independent_acceptance": "pending_BR-07",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (ART / "corpus" / "index.json").write_text(
        json.dumps(
            {
                "card_id": "E01-T9-CORPUS",
                "source_revision": rev,
                "evidence_status": "development_passed" if corpus_code == 0 else "failed",
                "manifest": "tests/fixtures/e01/corpus/manifest.json",
                "focused_log": str(corpus_log_path.relative_to(REPO)),
                "user_flows": "docs/acceptance/artifacts/E01/user-flows/source-cli-smoke.md",
                "independent_label_review": "pending_BR-05",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": rev,
        "boundary_exit_code": boundary_code,
        "cache_exit_code": cache_code,
        "corpus_exit_code": corpus_code,
    }
    (ART / "br03-06-focused.log").write_text(
        json.dumps(summary, indent=2) + "\n\n" + boundary_log + "\n---\n" + cache_log + "\n---\n" + corpus_log,
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0 if boundary_code == cache_code == corpus_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
