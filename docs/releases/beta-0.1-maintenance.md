# Beta 0.1.x maintenance and patch release (BR-18)

Procedure for **0.1.0b2+** without widening beta scope. Entry gate: [beta-0.1.0b2-entry-criteria.md](beta-0.1.0b2-entry-criteria.md).

## Prior accepted artifact

| Field | Value |
|---|---|
| Version | `0.1.0b1` |
| Wheel SHA-256 | `d44d6da0e6fc667a26260896cd5f4d82c35b59f8126e65ce38d92d9a8e97be24` |
| Fixture | [prior_accepted_artifact.json](../acceptance/artifacts/E07/prior_accepted_artifact.json) |

## Rehearsal steps (development)

1. Create venv A; `pip install --no-index` the pinned `0.1.0b1` wheel (from GitHub Release or [tests/fixtures/e07/](../../tests/fixtures/e07/)).
2. Record `pullraptor --help` and import path.
3. **Update simulation:** install same wheel again (or candidate `0.1.0b2` wheel when it exists) into venv B; verify import path not from source tree.
4. **Rollback:** reinstall pinned `0.1.0b1` bytes; verify SHA-256 matches prior artifact.
5. Save logs under [docs/acceptance/artifacts/E07/install/](acceptance/artifacts/E07/install/).

Automated subset: `PYTHONPATH=src python3.12 -m unittest tests.test_installed_artifacts.TestInstalledArtifacts.test_br18_prior_wheel_reinstall_rollback -v`

## Claims

- Rehearsal proves **local pip reinstall/rollback** against pinned bytes only.
- Does not authorize customer update/rollback marketing until BR-18 evidence is independently reviewed and a second release exists.
- `pullraptor-publish` remains beta-gated.
