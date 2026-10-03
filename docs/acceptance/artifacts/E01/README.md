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
| `requirement-assertion-fixture-map.json` | Coordinator map for E01-T9-MAP (Step 1); all runtime rows `not_run`; may include `runtime_subset` after collection |
| `downstream-fixture-schedule.json` | Automatable card schedule from the requirement map and cache/output overlay |
| `cache-output-assertion-map.runtime-xref.json` | Links static Task 7–8 map revision to separately collected runtime subset |
| `cache/`, `output/`, `boundaries/`, `corpus/`, `benchmark/` | Placeholder `index.json` until assigned downstream cards save fixtures |

Regenerate runtime subset and downstream schedules (trusted dev environment):

```bash
PYTHONPATH=src python3.12 scripts/e01_collect_acceptance.py
python3.12 scripts/e01_build_requirement_map.py
python3.12 scripts/e01_validate_requirement_map.py
python3.12 scripts/e01_micro_benchmark.py
python3.12 scripts/e01_refresh_downstream_artifacts.py
```

Rebuild the requirement map alone after editing static inventory or overlay inputs:

```bash
python3.12 scripts/e01_build_requirement_map.py
python3.12 scripts/e01_validate_requirement_map.py
```

Future scoped outputs: saved fixtures under the card directories above and `independent-review.md` when assigned.
