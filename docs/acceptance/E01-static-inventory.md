# E01 supplemental static inventory

Date: 2026-10-03. Status: historical static inspection at the pinned revision below; E01 Task 9 assertion mapping remains incomplete. This inspection supplies no runtime pass or independent product acceptance. Preserve separately collected runtime evidence in the primary E01 acceptance record; declarations cannot validate its broader criterion claims.

## Revisions, scope and method

Source, tests, plan and trusted base inspected at `132f817e96dfd9de21051c9389a7112b6dc6f084`. E01 scope: offline Python 3.12 kernel, PY001–PY003 advisory patterns, immutable comparison, scope/evidence, bounded ingestion/process/output, private parser cache and JSON/Markdown/SARIF. AI, publisher and MCP source modules were inventoried separately as adapters, not credited to E01 acceptance.

The coordinator read immutable Git blobs and parsed test declarations with Python stdlib `ast`, under `python3 -I -S`. It did not import PullRaptor, run its development suite, execute reviewed target code, install packages, benchmark or call any provider. The exact names/paths/lines and file digests are saved in the [static inventory](artifacts/E01/2026-10-03-static-inventory.json). Digests locate the inspected bytes; they grant no correctness or approval authority.

Observed inventory: 17 production Python modules, of which 14 are assigned to E01; 16 test modules with 125 declared test methods across all existing scopes. E01 Tasks 1–8 name 106 distinct tests; 68 exact names occur in the inspected declarations and 38 do not. An absent name does not prove missing behavior: alternate tests and their assertions still require manual mapping. A present name does not prove a meaningful fixture or passing result.

## Named-test mapping, not behavior acceptance

| E01 task | Planned exact names | Declarations located | Exact names absent | Next review |
|---|---:|---:|---:|---|
| 1: records/codec/canonical output | 10 | 10 | 0 | Verify strict limits/types, authority rejection, failure variants and expected assertion outcomes |
| 2: trusted policy | 5 | 5 | 0 | Verify base-policy provenance, precedence, invalid minimum limits and denial outcomes |
| 3: snapshot/process/diff | 20 | 13 | 7 | Map ambient config, lazy-fetch/missing/multiple bases, filename/handle and output-bound cases |
| 4: facts/receipts/import resolution | 21 | 18 | 3 | Map neutral worker CWD, duplicate fields and unresolved-context behavior |
| 5: pattern restraint | 4 | 4 | 0 | Count and pin per-rule positive/counterexample fixtures and claim boundaries |
| 6: evidence/scope/differential behavior | 14 | 10 | 4 | Map wrong revision/capability, ambiguous rename, incomplete discovery and locally sound claims under partial coverage |
| 7: cache/incremental orchestration | 16 | 2 | 14 | Check alternate names without assuming equivalence; map foreign/shared/changed-extractor/mutation and scope-growth cases |
| 8: CLI/render/recovery/output failure | 16 | 6 | 10 | Map egress, escape/navigation, omissions, failure-finalization and recovery assertions |

The JSON lists every named item and located declaration. Full requirement/assertion mapping is pending, including unnamed adverse behaviors in the plan and evaluation contract. Historical checked boxes were not used as passing evidence.

## Acceptance criteria and missing evidence

| Criterion | Expected evidence | Command / result | State |
|---|---|---|---|
| E01-A1 | Every required behavior/adverse case mapped to exact assertions, fixtures and fresh outputs; scope/process/records/presentation/zero-egress invariants | Required verification command: `PYTHONPATH=src python3.12 -m unittest discover -s tests -v`; not executed by this inspection. Separately collected suite output requires assertion/fixture reconciliation. | `not_run` in this static inspection |
| E01-A2 | Completed clean/warm/corrupt/absent canonical equality, mutation/replay receipts and ≥10 positive/10 counterexample-or-ambiguous fixtures per initial rule | Fixture IDs, full report comparisons, partial replay and rule-corpus counts not yet independently mapped or run; command selection pending that inventory | `not_run` |
| E01-A3 | Runtime/dependency/size inventory, ≥30 pinned cold/warm benchmark repetitions on the specified 2-vCPU/4-GiB fixture, p95/RSS/enforcement and independent local-flow decision | Supported runtime/runner/fixture/resource observations and independent decision absent; no benchmark executed | `not_run` |

The JSON inventory is a raw static artifact only. This inspection did not produce test output, mutation reports, corpus labels, resource measurements or independent acceptance artifacts; preserve and review any separately collected evidence in the primary E01 record. The E01/E02 usefulness pilot additionally gates wider language/security expansion; it is not a prerequisite for this inventory or for gathering E01 acceptance evidence.

## Next bounded work and independent review

Continue Q01 in the [worker dispatch queue](../worker-dispatch.md): review the located test bodies, map equivalent alternate names with exact assertion/fixture references, inventory every unnamed adverse behavior, and pin the expected results and unrun commands. Task 7–8 body mapping lives in [cache/output assertion map](artifacts/E01/2026-10-03-cache-output-assertion-map.md); the merged coordinator inventory is [requirement-assertion-fixture-map.json](artifacts/E01/requirement-assertion-fixture-map.json) (rebuild via `scripts/e01_build_requirement_map.py`). Create scoped correction tasks for demonstrated defects; do not write production fixes as an unassigned side effect of this inventory.

Only after the coordinator assigns verification in a suitable trusted development environment may runtime evidence be collected. Reviewed target-repository execution remains separately gated by E06. An independent reviewer must assess all required revision-bound evidence before E01 can be accepted. Current independent acceptance decision: **pending**.
