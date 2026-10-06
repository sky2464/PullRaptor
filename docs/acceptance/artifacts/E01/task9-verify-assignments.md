# E01 Task 9 verify assignments (post-0.1.0b1)

Beta subset acceptance for E01 is recorded; full E01-A1–A3 remain open. Parallel **verify** assignments below do not widen beta customer claims.

| Card | Mode | Owner | Command / artifact | Acceptance IDs |
|---|---|---|---|---|
| E01-T9-MAP | verify | Kernel evidence owner | Reconcile [requirement-assertion-fixture-map.json](../artifacts/E01/requirement-assertion-fixture-map.json) against [2026-10-03-cache-output-assertion-map.md](../artifacts/E01/2026-10-03-cache-output-assertion-map.md) | E01-A1 |
| E01-T9-CACHE | verify | Cache owner | `PYTHONPATH=src python3.12 -m unittest tests.test_cache -v` + refresh cache receipts under `docs/acceptance/artifacts/E01/cache/` | E01-A2 |
| E01-T9-OUTPUT | verify | Output owner | `PYTHONPATH=src python3.12 -m unittest tests.test_output tests.test_render -v` | E01-A1 |
| E01-T9-CORPUS | verify | Rules owner | `PYTHONPATH=src python3.12 -m unittest tests.test_rules -v` | E01-A1 |
| E01-T9-BENCH | verify | Benchmark owner | `python3.12 scripts/e01_benchmark.py` (host Python 3.12) | E01-A3 |
| E01-T9-ACCEPT | verify | Independent reviewer | Separate session; implementer excluded | E01-A1–A3 |

BR-02 rebaseline: run `python3.12 scripts/generate_beta_evidence_index.py` at the assigned code OID after map or suite changes; compare [beta-0.1-evidence-index.json](../../releases/beta-0.1-evidence-index.json) to manifest BR fields.
