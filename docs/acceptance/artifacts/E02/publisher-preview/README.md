# E02 publisher integration preview evidence (E02-T2-INTEGRATE)

Construction evidence for bounded `publish_report` / CLI integration with **mocked** GitHub transport only.

## Artifacts

| Path | Role |
|---|---|
| [tests/fixtures/e02/publisher/](../../../../tests/fixtures/e02/publisher/manifest.json) | Denied-gate and preview-only scenarios |
| [tests/test_publisher.py](../../../../tests/test_publisher.py) | Card-named integration tests |
| [tests/test_publisher_fixture_scenarios.py](../../../../tests/test_publisher_fixture_scenarios.py) | Fixture replay |
| [validation-log.txt](validation-log.txt) | Captured unittest output |

## Validation command

```bash
PYTHONPATH=src python3.12 -m unittest tests.test_publisher tests.test_publication_contract tests.test_render tests.test_publisher_fixture_scenarios -v
```

## Gates

- [tests/test_beta_entrypoints.py](../../../../tests/test_beta_entrypoints.py) must keep `pullraptor-publish` at exit **2** without `PULLRAPTOR_DEV_ADMIT_EXTENDED=1`.
- E02-A2/A3 independent acceptance and live publication remain `not_run`.
