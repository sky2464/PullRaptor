# E02 local capture construction evidence (partial)

Trusted development verification for card `E02-T1-CAPTURE` at the implementing PR revision.

## Scope covered

- Executable file modes preserved in workdir capture (`100755` vs `100644`).
- Parent symlink refusal on admitted relative paths.
- Aggregate `max_total_bytes` enforcement separate from Git plumbing stdout bounds.
- Unmerged index detection via `git ls-files -u`.
- Repository index identity change during capture surfaces `capture_race`.

## Not claimed

- E02-A1 acceptance, hostile filesystem profiles, or independent review.
- Full E02-D02 sealing fixture corpus beyond the named unit tests.

## Command (assigned card)

```bash
PYTHONPATH=src:. python3.12 -m unittest tests.test_local_snapshot tests.test_working_tree tests.test_snapshot -v
```
