#!/usr/bin/env python3.12
"""Collect per-case development evidence without promoting criteria or beta receipts."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
try:
    from scripts.e01_build_requirement_map import assertion_inventory, source_identity
except ModuleNotFoundError:
    from e01_build_requirement_map import assertion_inventory, source_identity

REPO = Path(__file__).resolve().parents[1]
ART = REPO / 'docs/acceptance/artifacts/E01/full'
MODULES = ('tests.test_models', 'tests.test_config', 'tests.test_process', 'tests.test_snapshot',
           'tests.test_diff', 'tests.test_python_facts', 'tests.test_rules', 'tests.test_evidence',
           'tests.test_cache', 'tests.test_kernel', 'tests.test_cli', 'tests.test_render',
           'tests.test_e01_offline_boundaries', 'tests.test_e01_evidence_integrity',
           'tests.test_e01_core_regressions', 'tests.test_e01_output_contract')


def collect_suite(suite: unittest.TestSuite) -> tuple[list[dict], str]:
    """Keep every failure/skip/subcase; successful aggregate exit is insufficient."""
    bodies = {body['test_id']: body for body in assertion_inventory(REPO)}
    records = {}
    class CaseResult(unittest.TextTestResult):
        def startTest(self, test):
            super().startTest(test)
            records[test.id()] = {**bodies.get(test.id(), {}), 'test_id': test.id(),
                                  'result': 'not_run', 'subcases': []}
        def addSuccess(self, test):
            super().addSuccess(test)
            if records[test.id()]['result'] != 'failed':
                records[test.id()]['result'] = 'passed'
        def addFailure(self, test, err):
            super().addFailure(test, err)
            records[test.id()]['result'] = 'failed'
        def addError(self, test, err):
            super().addError(test, err)
            records[test.id()]['result'] = 'failed'
        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            records[test.id()]['result'] = 'not_run'
            records[test.id()]['reason'] = reason
        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            records[test.id()]['subcases'].append({'id': str(subtest), 'result': 'failed' if err else 'passed'})
            if err:
                records[test.id()]['result'] = 'failed'
    output = io.StringIO()
    unittest.TextTestRunner(stream=output, verbosity=2, resultclass=CaseResult).run(suite)
    return list(records.values()), output.getvalue()


def _git_revision() -> str:
    return subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'],
                                   env={'PATH': '/opt/homebrew/bin:/usr/bin:/bin'}, text=True).strip()


def collect(output_dir: Path, modules: tuple[str, ...] = MODULES) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    before = source_identity(REPO)
    cases, log = collect_suite(unittest.defaultTestLoader.loadTestsFromNames(modules))
    after = source_identity(REPO)
    if before != after:
        for case in cases:
            if case['result'] == 'passed': case['result'] = 'stale'
    fixtures = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((REPO / 'tests/fixtures/e01').rglob('*')) if path.is_file()}
    payload = {'schema': 'pullraptor-e01-case-receipts/2', 'collected_at': datetime.now(timezone.utc).isoformat(),
               'product_source': before, 'product_source_after': after, 'evidence_revision': _git_revision(),
               'runtime': {'python': platform.python_version(), 'executable': sys.executable, 'platform': platform.platform()},
               'fixture_manifest': fixtures, 'cases': cases, 'modules': list(modules),
               'independent_acceptance': 'pending', 'claim_limit': 'Development cases only; adequacy and independent acceptance separate.'}
    (output_dir / 'case-receipts.json').write_text(json.dumps(payload, indent=2) + '\n')
    (output_dir / 'development-tests.log').write_text(log)
    return int(any(case['result'] in {'failed', 'stale'} for case in cases))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ART)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return collect(args.output_dir)
    # Worker development tests receive no ambient credentials or shared caches.
    with tempfile.TemporaryDirectory(prefix='pullraptor-e01-verification-') as home:
        env = {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin', 'HOME': home,
               'PYTHONPATH': f'{REPO / "src"}{os.pathsep}{REPO}', 'LC_ALL': 'C', 'LANG': 'C',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', '--output-dir',
                               str(args.output_dir.resolve())], cwd=REPO, env=env, timeout=300)
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
