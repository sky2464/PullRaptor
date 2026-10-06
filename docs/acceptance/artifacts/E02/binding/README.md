# E02 publication binding construction evidence (E02-T2-BIND)

Trusted development verification for card `E02-T2-BIND` at the implementing revision. This corpus supports **construction** only; E02-A2 independent acceptance remains `not_run`.

## Artifacts

| Path | Role |
|---|---|
| [tests/fixtures/e02/publication-binding/](../../../../tests/fixtures/e02/publication-binding/) | Immutable adverse and authorized scenarios |
| [tests/test_publication_contract.py](../../../../tests/test_publication_contract.py) | Unit tests named in build card |
| [tests/test_publication_binding_fixtures.py](../../../../tests/test_publication_binding_fixtures.py) | Replays fixture JSON through `validate_publication` |
| [validation-log.txt](validation-log.txt) | Captured unittest output at evidence refresh |

## Publisher integration (E02-T2-INTEGRATE)

`src/pullraptor/publisher.py` invokes `validate_publication` before preview and again immediately before owned comment writes. Markdown overrides are ignored; rendering uses `render_markdown` only. Live publication remains gated by beta admission and E02 acceptance.

## Validation command

```bash
PYTHONPATH=src python3.12 -m unittest tests.test_publication_contract tests.test_publication_binding_fixtures tests.test_publisher -v
```

## Not claimed

- Customer-visible `pullraptor-publish` beta scope (still refused by default).
- E02-T3 lifecycle/writes, hostile CI template, or usefulness pilot acceptance.
