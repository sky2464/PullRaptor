"""Acceptance harness regressions: bounded fixture and incomplete-run honesty."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import e01_benchmark as benchmark
from scripts.generate_e01_synthetic_10k_fixture import generate_fixture
from tests.helpers import make_repo


class TestE01Benchmark(unittest.TestCase):
    def test_benchmark_manifest_exact_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = generate_fixture(Path(directory))
            self.assertEqual(fixture.entry_count, 10000)
            self.assertEqual(fixture.byte_total, 134217728)
            rows = subprocess.check_output(
                ['git', '-C', str(fixture.root), 'diff', '--numstat', fixture.base_ref, fixture.head_ref],
                text=True,
            ).splitlines()
            self.assertLessEqual(len(rows), 20)
            self.assertLessEqual(sum(int(row.split('\t')[0]) + int(row.split('\t')[1]) for row in rows), 2000)

    def test_benchmark_partial_runs_not_latency_success(self):
        repo = make_repo({'app.py': b'def f():\n    return 1\n'})
        try:
            head = repo.commit({'app.py': b'def broken(:\n'})
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                benchmark._review_once(repo.root, repo.commit_ids[0], head, warm=False)
        finally:
            repo.cleanup()

    def test_nearest_rank_p95_includes_29th_of_30(self):
        self.assertEqual(benchmark._p95(list(range(1, 31))), 29)


if __name__ == '__main__':
    unittest.main()

class TestAcceptanceMeasurements(unittest.TestCase):
    def test_benchmark_records_all_30_samples(self):
        from scripts.e01_acceptance_measure import summarize
        with self.assertRaisesRegex(ValueError, '30'):
            summarize([{'exit_code': 0, 'seconds': 1.0, 'rss_bytes': 1024, 'canonical_sha256': 'a' * 64}] * 29)

    def test_benchmark_partial_samples_cannot_pass_budget(self):
        from scripts.e01_acceptance_measure import summarize
        samples = [{'exit_code': 0, 'seconds': 1.0, 'rss_bytes': 1024, 'canonical_sha256': 'a' * 64} for _ in range(30)]
        samples[9]['exit_code'] = 2
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            summarize(samples)

    def test_benchmark_completed_canonical_disagreement_rejected(self):
        from scripts.e01_acceptance_measure import summarize
        samples = [{'exit_code': 0, 'seconds': 1.0, 'rss_bytes': 1024, 'canonical_sha256': 'a' * 64} for _ in range(30)]
        samples[4]['canonical_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'canonical'):
            summarize(samples)
