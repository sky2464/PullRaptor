# Source-CLI user flow smoke (implementer-collected)

Date: 2026-10-05. **Independent review:** pending.

## Flow: exact base/head Markdown review

Command pattern (representative; run against licensed fixtures in CI):

`PYTHONPATH=src python3.12 -m pullraptor --repo <fixture> --base <base> --head <head> --format markdown`

Evidence: `tests/test_cli.py` development suite (passed in `unittest_discover_verbose.log`).

## Excluded from beta user-flow claim

- `--staged` / `--workdir` flows (see `tests/test_working_tree.py` with dev override only)
- Installed-artifact user flows without source checkout: owned by BR-10 (**partial** on construction host via `tests/test_installed_artifacts.py`)
