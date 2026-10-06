# Beta candidate regression record

Date: 2026-10-05. Revision: `6f1b9d370f6332e88675d3bf2b681713b6840e44`.

| Check | Command | Result |
|---|---|---|
| Development suite | `PYTHONPATH=src python3.12 -m unittest discover -s tests -v` | OK (384 tests, 1 skipped) |
| Beta entrypoint containment | `tests/test_beta_entrypoints.py` | OK |
| Release provenance | `tests/test_release_provenance.py` | OK (in suite) |
| Installed artifact parity | `tests/test_installed_artifacts.py` | OK (construction host; 1 skip) |

## Classified skips

- `test_update_rollback_prior_accepted_artifact` — expected **not_run** (no prior accepted artifact; BR-18)

## Introduced changes on branch

- `pullraptor.beta_admission` gates excluded beta interfaces; E02/E08 tests set `PULLRAPTOR_DEV_ADMIT_EXTENDED=1`.
