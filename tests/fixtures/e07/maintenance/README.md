# Unpublished BR18 maintenance fixture

This is a test candidate, not a release. Public package metadata remains `0.1.0b1`.

`candidate-provenance.json` pins trusted source `48bef09d985fbeb42749d1cc6238c74429616a25`, the private fixture commit/tree, source tar/bundle and wheel hashes. `candidate-source.bundle` preserves that actual private Git commit. `candidate-source.tar` is its exact Git archive. The harness verifies the commit/tree, archive bytes, all source files and packaged code independently of the manifest's stated hashes.

The fixture changes only `pyproject.toml` and `src/pullraptor/__init__.py` to `0.1.0b2.dev0`, and adds an inert `maintenance_fixture.py` identity module. All three changes have before/after identities. It adds no runtime dependency or customer updating behavior. The accepted b1 wheel and prior acceptance marker are untouched.

Rebuild from an operator-owned reviewed offline wheelhouse:

```sh
python3.12 scripts/maintenance_rehearsal.py --source . \
  --output docs/acceptance/artifacts/E07/maintenance/macos-arm64 \
  --wheelhouse .superpowers/sdd/acceptance-maintenance-closure/wheelhouse \
  --prepare-candidate tests/fixtures/e07/maintenance
```

Build-only tools: pip 26.2.1 (MIT), setuptools 84.0.0 (MIT), wheel 0.48.0 (MIT), packaging 26.0 (Apache-2.0 OR BSD-2-Clause). Wheel's active packaging >=24.0 requirement is satisfied by the separately pinned packaging wheel. No setuptools optional extras are admitted. Tool wheel SHA-256 values are frozen in the harness and provenance ledger. Customer scenario venvs install only pip and PullRaptor, never those other build tools.
