# E01 independent acceptance review (beta 0.1.x subset)

Date: 2026-10-06. **Candidate source OID:** `f834f19e9b48c90fea35338c6940004b6a5fc459` (wheel bytes pinned; docs-only commits through `d56aae6` do not change archived product tree at `f834f19`). **Scope:** [docs/releases/beta-0.1-scope.json](../../../releases/beta-0.1-scope.json).

**Reviewer:** `sme_reviewer_agent_e01_2026_10_06` (independent of PRs #55–#58 implementer; persona [docs/personas/reviewer.md](../../../personas/reviewer.md)). **Decision:** **accepted** for the declared beta E01 subset only.

## Reproduction (reviewer environment)

| Step | Command / artifact | Result |
|---|---|---|
| Full development suite | `PYTHONPATH=src:. python3.12 -m unittest discover -s tests` | **passed** (324 tests, 1 skipped) at collection HEAD `d56aae6` |
| Boundary/cache/corpus refresh | `python3.12 scripts/e01_refresh_acceptance_evidence.py` | **passed** (exit 0) |
| Offline network boundary | [offline-network-receipt.json](boundaries/offline-network-receipt.json), `tests/test_e01_offline_boundaries.py` | **passed** |
| Linux synthetic 10k benchmark | [linux-runner-measurements.json](../benchmark/linux-runner-measurements.json) | **passed** (`within_budget` cold/warm/RSS) |
| Cache/corpus indexes | [cache/index.json](../cache/index.json), [corpus/index.json](../corpus/index.json) | **development_passed** |

## E01-A1 / A2 / A3 (beta subset)

| Criterion | Status | Evidence |
|---|---|---|
| E01-A1 kernel determinism and boundaries | **passed** (beta subset) | Core kernel tests + offline socket refusal receipt; full Task 1–8 assertion map still **partial** for roadmap-complete E01 |
| E01-A2 cache trust and replay | **passed** (beta subset) | `tests/test_cache.py`, `tests/test_kernel.py`; focused [cache/focused-cache.log](../cache/focused-cache.log) |
| E01-A3 corpus, user flows, benchmarks | **passed** (beta subset) | Linux 10k measurements; `tests/test_rules.py`; user-flow smoke doc; separate held-out accuracy study **not_run** (by scope) |

## Adverse / trust checks

| Check | Status | Notes |
|---|---|---|
| Offline CLI denies network in boundary suite | **passed** | Socket patch test + subprocess CLI smoke |
| Malicious path/presentation (full fixture corpus) | **partial** | Unit coverage exists; dedicated raw boundary fixture dir still sparse |
| Independent reproduction | **passed** | Reviewer re-ran suite and refresh script on assigned host |

## Limitations (explicit)

- Full E01 package acceptance (all 106 planned assertion bodies, adverse-input class matrix, held-out accuracy study) remains **out of beta scope**.
- Benchmark host is GitHub `ubuntu-24.04` class, not an independently pinned 2-vCPU/4-GiB metal ledger.

## Disposition

- **accepted:** yes (beta 0.1.x subset only)
- **rejected:** no
- **pending:** no for beta subset; full E01 remains pending for later milestones
