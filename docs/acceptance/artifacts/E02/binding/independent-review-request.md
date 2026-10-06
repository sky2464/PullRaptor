# E02-A2 independent review request (publication binding)

**Status:** requested — not acceptance.

| Field | Value |
|---|---|
| Card | `E02-T2-BIND` |
| Acceptance scope | E02-A2 (publication context binding) |
| Implementer exclusion | Authors of PRs #41–#46 and binding fixture PR on `feat/e02-publisher-integration-evidence` |
| Persona | [docs/personas/reviewer.md](../../../personas/reviewer.md) |

## Reproduction

1. Check out the code revision recorded in [construction-receipt.json](construction-receipt.json).
2. Run:

```bash
PYTHONPATH=src python3.12 -m unittest tests.test_publication_contract tests.test_publication_binding_fixtures tests.test_evidence tests.test_models -v
```

3. Inspect immutable scenarios under [tests/fixtures/e02/publication-binding/](../../../../tests/fixtures/e02/publication-binding/manifest.json).

## Expected reviewer outcome

- Record pass/fail per scenario in a separate session artifact (do not self-accept as implementer).
- `not_run` remains valid for live GitHub publication; beta customers must still see `pullraptor-publish` refused without dev admission.

## Outputs (reviewer)

- Update `docs/acceptance/artifacts/E02/binding/independent-review.md` (create on review) and cross-link from `docs/acceptance/E02.md` when assigned.
