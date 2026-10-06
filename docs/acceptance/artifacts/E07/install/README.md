# E07 install evidence (beta wheel subset)

Linux x86_64 offline venv install smoke is produced by the `Record linux-x86_64 offline wheel install smoke` step in `.github/workflows/ci.yml` and uploaded as the `e07-linux-install-smoke` workflow artifact. It is development verification only until independent BR-10 acceptance.

macOS arm64 development verification uses `release/install_matrix.json` profile `python-3.12-macos-arm64-venv` with a non-placeholder `evidence_revision`.
