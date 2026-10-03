# E01 acceptance artifacts

Revision-bound evidence for [E01 acceptance record](../E01.md). Nothing here alone establishes product acceptance.

| Artifact | Role |
|---|---|
| `git_revision.txt` | Candidate commit for collected runtime subset |
| `test_inventory.json` | AST-derived test method list at collection time |
| `unittest_discover_verbose.log` / `unittest_exit_code.txt` | Historical full-suite run (subset evidence only) |
| `micro_benchmark.json` | Informational two-file timing; not the master-plan 10k fixture |
| `2026-10-03-static-inventory.json` | 106 planned test names vs declarations at pinned revision |
| `2026-10-03-cache-output-assertion-map.md` | Task 7–8 and unnamed cache/output static body review |
| `task7-task8-assertion-overlay.json` | Machine-readable Task 7–8 overlay consumed by the map builder |
| `requirement-assertion-fixture-map.json` | Coordinator map for E01-T9-MAP (Step 1); all runtime rows `not_run` |

Regenerate inventory and suite log:

```bash
PYTHONPATH=src python3.12 scripts/e01_collect_acceptance.py
```

Rebuild the requirement map after editing static inventory or overlay inputs:

```bash
python3.12 scripts/e01_build_requirement_map.py
python3.12 scripts/e01_validate_requirement_map.py
```

Future scoped outputs (empty until assigned cards run): `cache/`, `output/`, `corpus/`, `user-flows/`, `benchmark/`, `boundaries/`, `independent-review.md`.
