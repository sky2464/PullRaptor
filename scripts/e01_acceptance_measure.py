#!/usr/bin/env python3.12
"""Fresh-process E01 acceptance measurements; incomplete runs never pass budgets."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pullraptor.kernel import review
from pullraptor.models import FullReport, canonical_bytes
from scripts.e01_build_requirement_map import source_identity
from scripts.generate_e01_synthetic_10k_fixture import generate_fixture


def summarize(samples: list[dict]) -> dict:
    if len(samples) != 30:
        raise ValueError('30 raw samples are required')
    if any(s['exit_code'] not in (0, 1) for s in samples):
        raise ValueError('incomplete samples cannot satisfy latency budgets')
    if len({s['canonical_sha256'] for s in samples}) != 1:
        raise ValueError('completed canonical output disagrees')
    ordered = sorted(s['seconds'] for s in samples)
    return {'repetitions': 30, 'p95_seconds': ordered[math.ceil(.95 * 30) - 1],
            'peak_rss_bytes': max(s['rss_bytes'] for s in samples),
            'canonical_sha256': samples[0]['canonical_sha256']}


def explicit_environment() -> dict[str, str]:
    return {'PATH': os.environ.get('PATH', os.defpath), 'PYTHONPATH': f'{ROOT / "src"}:{ROOT}',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'PYTHONDONTWRITEBYTECODE': '1', 'PIP_NO_INDEX': '1', 'PIP_NO_CACHE_DIR': '1'}


def sample(repo: Path, base: str, head: str, warm: bool, profile: str) -> dict:
    started = time.perf_counter()
    report, deadline, limits = review(repo, base, head, exact_base=True, use_cache=warm,
                                      overrides={'profile': profile, 'cache_dir': '/tmp/pullraptor-e01-cache/' + hashlib.sha256(str(repo).encode()).hexdigest()})
    raw = canonical_bytes(report, limits=limits, deadline=deadline)
    code = report.execution.get('exit_code', 3) if isinstance(report, FullReport) else report.exit_code
    scale = 1 if sys.platform == 'darwin' else 1024
    return {'seconds': time.perf_counter() - started, 'exit_code': code, 'profile': profile,
            'rss_bytes': int(max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                 resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)) * scale,
            'canonical_sha256': hashlib.sha256(raw).hexdigest(), 'report_bytes': len(raw),
            'kind': report.kind, 'python': platform.python_version(),
            'cache_hits': report.execution.get('cache_hits', 0) if isinstance(report, FullReport) else 0,
            'cache_misses': report.execution.get('cache_misses', 0) if isinstance(report, FullReport) else 0}


def take_sample(repo: Path, base: str, head: str, warm: bool, profile: str) -> dict:
    command = [sys.executable, str(Path(__file__).resolve()), '--sample', '--repo', str(repo),
               '--base', base, '--head', head, '--profile', profile]
    if warm:
        command.append('--warm')
    proc = subprocess.run(command, env=explicit_environment(), cwd=ROOT, capture_output=True,
                          text=True, timeout=90)
    if proc.returncode:
        raise RuntimeError(f'sample failed ({proc.returncode}): {proc.stderr[-1000:]}')
    packet = json.loads(proc.stdout)
    packet['command'] = command
    packet['process_exit_code'] = proc.returncode
    return packet


def series(repo: Path, base: str, head: str, profile: str, log: Path | None = None) -> dict:
    def collect(warm):
        record = take_sample(repo, base, head, warm, profile)
        if log:
            with log.open('a') as stream:
                stream.write(json.dumps({'warm': warm, **record}) + '\n')
        return record
    cold = [collect(False) for _ in range(30)]
    # A separate complete warm-up makes every timed warm sample a genuine cache replay.
    priming = collect(True)
    warm = [collect(True) for _ in range(30)]
    c, w = summarize(cold), summarize(warm)
    if c['canonical_sha256'] != w['canonical_sha256'] or priming['exit_code'] not in (0, 1):
        raise ValueError('clean/warm canonical output or priming completeness disagrees')
    if profile == 'structural' and any(s['cache_hits'] == 0 for s in warm):
        raise ValueError('warm structural samples did not admit cached facts')
    peak = max(c['peak_rss_bytes'], w['peak_rss_bytes'])
    return {'base_oid': base, 'head_oid': head, 'profile': profile, 'cold': c, 'warm': w,
            'priming': priming, 'cold_samples': cold, 'warm_samples': warm,
            'within_budget': {'cold_p95': c['p95_seconds'] <= 30,
                              'warm_p95': w['p95_seconds'] <= 5,
                              'peak_rss': peak <= 536870912},
            'result': 'passed' if c['p95_seconds'] <= 30 and w['p95_seconds'] <= 5 and peak <= 536870912 else 'failed'}


def runner_identity(require_linux: bool) -> dict:
    root = Path('/sys/fs/cgroup')
    cpu = (root / 'cpu.max').read_text().strip() if (root / 'cpu.max').exists() else 'unavailable'
    memory = (root / 'memory.max').read_text().strip() if (root / 'memory.max').exists() else 'unavailable'
    network = sorted(p.name for p in Path('/sys/class/net').iterdir()) if sys.platform == 'linux' else []
    if require_linux:
        if sys.platform != 'linux' or platform.machine() != 'x86_64':
            raise ValueError('Linux x86_64 acceptance runner required')
        if cpu == 'unavailable' or cpu.split()[0] == 'max' or int(cpu.split()[0]) / int(cpu.split()[1]) != 2:
            raise ValueError('enforced 2-vCPU cgroup required')
        if memory != str(4 * 1024 ** 3) or network != ['lo']:
            raise ValueError('enforced 4-GiB and denied network required')
    return {'platform': sys.platform, 'architecture': platform.machine(), 'python': platform.python_version(),
            'git': subprocess.check_output(['git', '--version'], text=True).strip(),
            'cpu_max': cpu, 'memory_max': memory, 'interfaces': network,
            'rss_method': 'fresh review subprocess maximum of RUSAGE_SELF/RUSAGE_CHILDREN',
            'cgroup_enforcement_required': require_linux}


def oid(repo: Path, ref: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', ref],
                                    env=explicit_environment(), text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', action='store_true')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--base', default='HEAD~1')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--profile', choices=('structural', 'diff'), default='structural')
    parser.add_argument('--warm', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/e01-acceptance-measurements')
    parser.add_argument('--require-linux', action='store_true')
    args = parser.parse_args()
    if args.sample:
        print(json.dumps(sample(args.repo, args.base, args.head, args.warm, args.profile)))
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': 'pullraptor-e01-full-measurements/1', 'source_revision': oid(ROOT, 'HEAD'),
               'product_source': source_identity(),
               'runner': runner_identity(args.require_linux), 'independent_acceptance': 'pending'}
    fixture = generate_fixture(args.output / 'fixture')
    receipt['fixture'] = {'entries': fixture.entry_count, 'head_bytes': fixture.byte_total,
                          'base_oid': fixture.base_ref, 'head_oid': fixture.head_ref}
    if fixture.entry_count != 10000 or fixture.byte_total != 134217728:
        raise ValueError('benchmark fixture does not match the required scope')
    receipt['synthetic'] = series(fixture.root, fixture.base_ref, fixture.head_ref, 'structural', args.output / 'synthetic-samples.jsonl')
    receipt['real_repository'] = series(args.repo, oid(args.repo, args.base), oid(args.repo, args.head), 'diff', args.output / 'real-samples.jsonl')
    receipt['real_repository']['scope'] = 'PullRaptor owned real-repository generic diff; no semantic quality claim'
    adverse = args.output / 'adverse-source.py'
    adverse.write_text('value = ' + '[' * 10000 + '0' + ']' * 10000 + '\n')
    from pullraptor.python_facts import extract_python
    from pullraptor.models import Deadline, Limits
    started = time.monotonic()
    parsed = extract_python(adverse.read_bytes(), Limits(), Deadline(started, 30))
    receipt['adverse'] = {'source_sha256': hashlib.sha256(adverse.read_bytes()).hexdigest(),
                          'bytes': adverse.stat().st_size, 'seconds': time.monotonic() - started,
                          'result': 'passed' if parsed.content is None and parsed.diagnostics else 'failed',
                          'diagnostics': [d.code for d in parsed.diagnostics], 'expected': 'visible parse refusal, no execution'}
    modules = sorted((ROOT / 'src' / 'pullraptor').glob('*.py'))
    receipt['inventory'] = {'modules': len(modules), 'lines': sum(len(p.read_text().splitlines()) for p in modules),
                            'source_bytes': sum(p.stat().st_size for p in modules),
                            'runtime_python_dependencies': [], 'requirements': ['Python 3.12', 'Git'],
                            'enabled_scope': 'owned Python advisory review and generic diff; adapters included in source inventory'}
    (args.output / 'measurements.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'output': str(args.output / 'measurements.json'),
                      'synthetic': {k: receipt['synthetic'][k] for k in ('cold', 'warm', 'within_budget')},
                      'real': {k: receipt['real_repository'][k] for k in ('cold', 'warm', 'within_budget')}}))
    return 0 if receipt['synthetic']['result'] == receipt['real_repository']['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
