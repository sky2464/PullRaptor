# Beta 0.1.x release decisions

Date: 2026-10-06.

## Maintainer sign-off (BR-01)

| Field | Decision |
|---|---|
| Maintainer | `human_coordinator` |
| Scope | Approved as documented in [beta-0.1-scope.json](beta-0.1-scope.json) (offline wheel CLI, PY001–PY003, exact Git review; exclusions contained) |
| Package version | **`0.1.0b1`** |
| Tag | **`v0.1.0b1`** |
| Publication channel | GitHub Release on `sky2464/PullRaptor` |
| Candidate reviewed OID | `f834f19e9b48c90fea35338c6940004b6a5fc459` (product tree; version metadata aligned in follow-up commit) |
| Remote check | No existing `v0.1.0b1` release or tag on 2026-10-06 |
| Independent E01/E07 | Accepted for beta subset (2026-10-06 reviewer agents) |

---

## Historical implementer preparation (superseded by sign-off above)

Date: 2026-10-06. Candidate source revision: `3f725e3dbc65e9437ffd64a9e4586deb09f7ea8f` (merge of #55). Trusted base inspection: `8c2622e060b59f93c3482afec96bc472c5de3ac2`.

## Version and labeling

| Field | Proposed value | Notes |
|---|---|---|
| Human label | beta 0.1.x | Customer-facing series name |
| Python package version | `0.1.0b1` | Applied in `pyproject.toml` / `__version__` after maintainer sign-off |
| Git tag (if authorized) | `v0.1.0b1` | Must point at independently reviewed candidate; no overwrite of existing published artifacts |
| Published artifact check | No `v0.1*` tags or releases observed locally on 2026-10-05 | Maintainer must recheck remotes before publication |

Reconciling `0.3.0` metadata: roadmap package targets (E03=0.3) used development versioning; the first **customer** prerelease should adopt `0.1.0b1` to match the E01/E07 beta milestone. Apply version alignment only after BR-01 maintainer sign-off (BR-08 implements consistently).

## Included product surface (minimum)

- Wheel-installed **offline** Python **3.12.x** CLI (`pullraptor` console script).
- Exact committed Git revision review: `--repo`, `--base`, `--head`, `--exact-base`, `--profile structural|diff`, `--format markdown|json|sarif`, cache controls, `--ci`.
- Advisory Python rules **PY001**, **PY002**, **PY003** (structural/diff profiles as implemented).
- Generic diff summaries and coordinator-owned report schema v1 semantics.
- Private operator-owned cache (default on; `--no-cache` supported).

## Explicit exclusions (contained, not advertised)

Excluded interfaces remain in the wheel for adapter development but **refuse by default** via `pullraptor.beta_admission` unless `PULLRAPTOR_DEV_ADMIT_EXTENDED=1` (development only). See `docs/releases/beta-0.1-entrypoints.json` and `tests/test_beta_entrypoints.py`.

- `pullraptor-publish`, GitHub CI publication, usefulness pilot (E02-A2–A4).
- `pullraptor-mcp`, CLI `--mcp`, editor/agent packages (E08).
- Local snapshot flows: `--staged`, `--workdir`, `--include-untracked` (E02-A1).
- Optional AI network transport (`--ai-endpoint` and related flags) (E03).
- Container image distribution (E07 container profile).
- Additional languages, modeled security, patch validation runner, preferences, service, enterprise, Azure (E04–E06, E09–E11).

## Platform profiles (candidates until BR-10)

| Profile ID | Platform | State at BR-01 |
|---|---|---|
| `python-3.12-linux-x86_64-venv` | linux-x86_64 | candidate / not_run |
| `python-3.12-macos-arm64-venv` | darwin-arm64 | candidate / development_verified on construction host only |
| `python-3.12-linux-x86_64-container` | container | excluded from beta scope |

## Owners (assignments proposed; coordinator confirms)

| Role | Proposed owner | Responsibility |
|---|---|---|
| Release maintainer | Human (coordinator) | BR-01 scope/version, BR-15 go/no-go |
| Release evidence owner | Implementer agent (this branch) | BR-02, BR-14 dossier assembly |
| Fixture owner | Implementer + coordinator | BR-05 corpus labels; independent label review pending |
| Platform owners | Human + CI hosts | BR-10 clean-machine installs |
| E01 independent acceptance reviewer | **Unassigned** | BR-07; cannot be implementer |
| E07 distribution acceptance reviewer | **Unassigned** | BR-13 |
| Publication operator | **Unassigned** | BR-16; requires BR-15 authorization |
| Verification environments | Python 3.12 sanitized venv; Git 2.4x; offline wheel install | Documented in `release/install_matrix.json` |

## Maintainer decisions still required

1. Confirm beta scope table and exclusions.
2. Approve package version `0.1.0b1` and tag naming.
3. Assign independent reviewers for BR-07 and BR-13.
4. Authorize publication (BR-15+) separately from this implementation work.

## Suggested first PR scope (coordinator)

**Include:** `docs/releases/`, `docs/acceptance/releases/`, beta-related `docs/acceptance/artifacts/E01/` and `E07/` receipts, `docs/install.md`, `CHANGELOG.md`, `src/pullraptor/beta_admission.py`, entrypoint containment edits (`__main__.py`, `publisher.py`, `mcp_server.py`), `tests/test_beta_entrypoints.py`, related test env fixes, `scripts/e01_benchmark.py`, `scripts/generate_beta_evidence_index.py`, `tests/fixtures/e01/`, coordinator updates to `docs/worker-dispatch.md`, `docs/release-tasks.json`, `Master-Plan.md`.

**Exclude unless separately assigned:** untracked E04–E11 preparation modules (`runner/`, `service/`, optional feature tests), unrelated roadmap stubs in the working tree.
