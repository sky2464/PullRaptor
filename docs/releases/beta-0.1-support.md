# Beta 0.1.x support (draft)

**Channel:** issue tracker / coordinator contact (not configured in-repo). **Scope:** offline wheel CLI per `docs/releases/beta-0.1-scope.json`.

## Reporting defects

Include: wheel SHA-256, Python version, Git version, exact `pullraptor` command, exit code, and redacted report JSON if applicable. Do not attach customer proprietary source unless policy allows.

## Security

Report suspected vulnerabilities through the project security contact when published; beta builds refuse excluded entrypoints by default (see `tests/test_beta_entrypoints.py`).

## Privacy

Default beta flow performs local analysis only; no telemetry is defined for the offline CLI.
