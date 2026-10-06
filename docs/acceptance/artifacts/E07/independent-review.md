# E07 independent distribution acceptance (beta wheel subset)

Date: 2026-10-06. **Candidate source OID:** `f834f19e9b48c90fea35338c6940004b6a5fc459`. **Wheel SHA-256:** `b1d8df90023868ba666408318d96a1075720082faf6a86c51e6af42ecc05f700`.

**Reviewer:** `sme_reviewer_agent_e07_2026_10_06` (independent of PRs #55–#58 implementer; separate session from E01 reviewer; persona [docs/personas/reviewer.md](../../../personas/reviewer.md)).

## Reproduction

| Step | Evidence | Result |
|---|---|---|
| Inventory | [docs/dependencies/E07.json](../../../dependencies/E07.json) | **passed** — setuptools 84.0.0 pinned with digest; kernel stdlib-only |
| Provenance | [two-build-comparison.json](../provenance/two-build-comparison.json), `release/build.py` git archive | **passed** — byte-identical wheels; distinct provenance refs |
| Independent digest check | Recomputed SHA-256 of committed wheel | **passed** — matches manifest |
| Install (development) | `tests/test_installed_artifacts.py` on Python 3.12 | **passed** (1 skip: no prior artifact for rollback) |
| Linux install receipt | [linux-x86_64-acceptance.json](../install/linux-x86_64-acceptance.json) | **passed** — workflow 37404240057; independent clean-machine sign-off still coordinator-owned |
| Beta containment | `tests/test_beta_entrypoints.py`, `scripts/ci_beta_install_smoke.sh` | **passed** |

## E07-A1 / A2 / A3 (beta subset)

| Criterion | Status | Notes |
|---|---|---|
| E07-A1 inventory and licenses | **passed** (subset) | Beta wheel subset only |
| E07-A2 provenance and reproducibility | **passed** (subset) | Independent origin recompute at review time |
| E07-A3 install and parity | **passed** (subset) | Linux CI + local install tests; container/update/rollback excluded |

## BR-11 recovery (beta subset)

| Item | Status |
|---|---|
| Disposable tabletop | **accepted for first GitHub Release beta** — [beta-0.1-recovery-rehearsal.json](../../../releases/beta-0.1-recovery-rehearsal.json) + [runbook](../../../releases/beta-0.1-recovery-runbook.md) |
| Live channel withdrawal | **not_run** until after BR-16/17 |

## Excluded from beta subset

Container image, update/rollback from prior accepted artifact (BR-18), GitHub publication workflow product acceptance.

## Packaging addendum (0.1.0b1)

After maintainer sign-off, metadata version aligned to `0.1.0b1` at source OID `097e9ae…`. Rebuilt wheel digest **`d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24`** (`pullraptor-0.1.0b1-py3-none-any.whl`). Packaging-only change; beta subset acceptance carries forward.
