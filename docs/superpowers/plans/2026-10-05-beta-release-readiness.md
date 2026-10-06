# Beta 0.1.x Release Readiness Implementation Plan

> **For agentic workers:** Use the execution method selected by the human/coordinator and the [dispatch contract](../../worker-dispatch.md); do not infer delegation or execution authority from this plan. Steps use unchecked checkboxes until evidence exists.

**Goal:** Produce an independently accepted, installable beta 0.1.x and carry its exact artifacts through authorized publication and customer-path verification.

**Architecture:** Reuse the E01 kernel and E07 distribution child tasks, then add cross-package scope, evidence, containment and release operations. The coordinator owns requested scope and pins each assignment; separate reviewers accept behavior and distribution. Optional delivery tracks join only through their own consumed acceptance gates.

**Tech Stack:** Python 3.12.x, stdlib kernel, Git, reviewed build-only tools, declared platform environments; no new runtime dependency is admitted by this document.

**Spec:** [Parent specification](../specs/2026-10-03-pullraptor-design.md), [E07 distribution specification](../specs/2026-10-03-e07-release-distribution.md), [evaluation contract](../../evaluation.md), and [Master Plan](../../../Master-Plan.md).

Date: 2026-10-05. Source/trusted-main inspection: `8c2622e060b59f93c3482afec96bc472c5de3ac2`; local checkout: `6f1b9d370f6332e88675d3bf2b681713b6840e44`. Local uncommitted E04/E05/E06/E11 work is preparation evidence only and excluded from this baseline. The machine-readable [release queue](../../release-tasks.json) supplements the 71 historical [build cards](../../build-tasks.json); it does not rewrite their pinned observations. Re-pin source, docs and trusted base at actual dispatch.

## Global constraints

- Zero third-party packages in the deterministic kernel; Git executable required; Python 3.12.x only until parser parity admission.
- Never execute reviewed target code in analysis; development verification needs a separate scoped assignment and sanitized environment.
- CI policy derives from trusted base; untrusted content cannot supply scope, origins, executable config or release authority.
- Keep competing names/domains out of project records; own algorithms and inspect licenses before admission.
- Preserve incomplete/unknown/conflicting/stale results. Completed tests, hashes and graphs are not independent acceptance.
- Default bounds: 10,000 entries; 2,097,152 bytes/blob; 134,217,728 bytes/snapshot; 60 seconds/review with a 2-second finalization reserve; 8,388,608 bytes/report.
- All commits on `feat/`, `fix/`, `chore/` or `docs/` branches; integrate through CI-verified PRs. Keep main plus one or two active work branches, pruning merged branches after checking ownership/worktrees.
- This request updates planning only. No release publication, infrastructure activation, remote source transfer or package acceptance is granted.

## Release scope and gates

The proposed first milestone is a wheel-installed offline Python CLI beta: generic diff, advisory PY001–PY003, exact committed Git comparisons, declared JSON/Markdown/SARIF and private-cache semantics. BR-01 requires maintainer scope confirmation before downstream implementation; it must record profiles and any additional capabilities. Broad E01–E11 goals remain intact. A wheel-only first beta accepts an E07 **subset**, not the whole distribution package. Container/update/rollback and other excluded scopes remain visible and owned.

| Included capability | Additional mandatory work before claiming support |
|---|---|
| Staged/unstaged/unsaved local changes | E02-A1 race/sealing/storage/capture-consumer evidence and independent scoped decision |
| GitHub CI or comment publication | All consumed E02-A1–A4 evidence, actual same-repository/fork isolation and publisher binding/lifecycle/reconciliation; the usefulness pilot below |
| Container | E07 image build/runtime/license inventory, independent origin, real offline install and source/wheel/image parity; a non-root image alone does not accept hostile CI isolation |
| AI context/chat | E03-A1–A3, consent/transport/redaction/prompt-injection and pinned proposal provenance |
| Additional language/security rules | Applicable E04/E05 criteria, held-out capability evidence and license/runtime admission; no syntax-only semantic claim |
| Patches/runner/preferences | Applicable E06 criteria and >=50 validation scenarios; actual reviewed-target launch remains blocked until independent E06-A2 isolation acceptance |
| Editor/plugins/local or remote MCP | Applicable E08 criteria/client-session matrix; local snapshots need E02, remote authority needs E10/E11 essentials |
| Azure/service/enterprise | Applicable E09/E10/E11 criteria and separately accepted operational/user flows; no local stub-to-hosted claim |

The early E01/E02 usefulness pilot remains required before wider language/security/delivery expansion: at least 30 eligible Python PRs, three repositories and two maintainers, with noise/time thresholds agreed before collection, exclusions and completion/gap/noise metrics saved. It is mandatory for a beta claiming GitHub publication, and is not replaced by the offline local user-flow evidence. Full defect accuracy/default blocking requires the separately owned study: at least 200 revision pairs from 20 repositories, repository-held-out splits, independent labels and applicable n>=100/95% precision lower bound >=0.90 plus all other evaluation controls. Initial beta patterns remain advisory; do not turn lack of that study into an accuracy claim.

Ready for release requires BR-01–14 passed for frozen scope. BR-15 records human go/no-go and publication authorization. BR-16 publishes; BR-17 verifies the actual public install path. BR-18 is conditional on a later patch/update/rollback claim and has no fabricated prior-artifact prerequisite for the first beta. Any failed required criterion blocks only its consuming operation and has an owner; independent preparation may continue.

## Review focus

1. Bundled publisher/MCP/security options can remain callable despite narrow marketing: BR-08 enumerates and tests every shipped interface.
2. Builder environment strings and a supplied source OID can describe different bytes: BR-09 rejects mismatched trees and independently checks origin.
3. Mocked report rendering can pass while installed review is broken: BR-10 executes actual installed analysis without source imports.
4. Historical passing artifacts can survive source/profile changes: BR-02 and BR-14 record invalidation and required recollection.
5. First beta has no accepted prior release: BR-10 checks first-install recovery, BR-13 excludes unrun update promises, BR-18 later earns them.

## File ownership and interfaces

`docs/release-tasks.json` owns release-task metadata/dependencies, while existing build cards and child plans own code interfaces and assertion details. `docs/releases/beta-0.1-scope.json` will hold the confirmed command/rule/artifact/platform inventory; `beta-0.1-evidence-index.json` will bind each obligation to owner, source/docs/fixture/policy/runtime IDs, command, expected/observed result, raw output and passed/failed/not_run/stale state. `docs/acceptance/releases/beta-0.1.md` will hold independent decisions, exact candidate/source and artifact identity, exclusions, readiness, authorization and published verification as distinct states. Output paths below are proposed work, not assumed inputs or evidence. Allowed modification paths at dispatch are each release card’s output/allowed_modify_paths plus its referenced existing child cards’ outputs; reproduced-defect source changes require coordinator-narrowed paths. BR-01 produces `docs/releases/beta-0.1-capability-gates.json`; BR-08 inventories enabled machine-readable conditional rows and preserves pending admission during bounded construction; BR-14 consumes their final independent acceptance. Missing/stale/rejected optional evidence cannot become readiness by completing the fixed BR tasks. Candidate build/install cannot require its own future acceptance; actual activation, remote transfer and target execution retain their separate gates.

Each implementation card uses its existing child plan interfaces. Write a meaningful failing regression before fixing a reproduced code defect, run the focused check after the minimal fix, then capture the required user-flow evidence. Commit only owned paths on a scoped PR branch; re-pin downstream assignments after merging. Preparation/review/release tasks produce records rather than artificial unit tests. All commands below are future assigned checks; none ran for this documentation update.

## Ordered release tasks

### BR-01: Freeze beta scope, version and supported profiles

**Owner:** Coordinator/release maintainer. **Mode:** prepare. **Status:** pending.

**Prerequisites:** none; existing cards: release coordination task.

**Files / interfaces:** Consumes `Master-Plan.md`, `pyproject.toml`, `src/pullraptor/__init__.py`, `release/install_matrix.json`, `docs/research/2026-10-03-capability-review.md`; produces/modifies `docs/releases/beta-0.1-scope.json`, `docs/releases/beta-0.1-decisions.md`, `docs/releases/beta-0.1-capability-gates.json`.

**Operation gate:** Scope decision by maintainer; no publishing authorization inferred.

- [ ] **Step 1:** Record included commands, rules, report schema, language tiers, artifacts, platforms, runtime and exclusions for all F01–F32 and delivery amendments. Proposed minimum: wheel-installed offline Python 3.12 CLI, generic diff and advisory PY001–PY003; exact Git revisions. Linux x86_64 and macOS arm64 are candidates, supported only after BR-10 evidence. Produce capability-gates.json resolving every included or executable interface to the conditional_requires rows, exact criterion scope, existing cards, evidence path and independent decision; mark excluded interfaces and their tested containment. No worker may omit an enabled gate.
- [ ] **Step 2:** Choose the first package prerelease version and tag with the maintainer. Recommended package version 0.1.0b1, human label beta 0.1.x; reconcile current 0.3.0 metadata and client versions deliberately. Check existing published artifacts/tags before allowing a lower version; never overwrite an existing artifact.
- [ ] **Step 3:** Name release owner, fixture owner, platform owners, independent acceptance reviewer and publication operator; assign verification environments and release channels. Container, staged/workdir review, publishing, MCP and optional adapters require their scope-specific acceptance or explicit exclusion/disablement.

**Exit evidence:** Maintainer-approved scope/version/profile record with no unsupported advertised capability; owners and consumed gates recorded. No product code version changed by this planning update.

### BR-02: Rebaseline assertions and evidence at the candidate revision

**Owner:** Coordinator/evidence owner. **Mode:** prepare/verify. **Status:** pending.

**Prerequisites:** BR-01; existing cards: E01-T9-MAP, E01-T9-RECORDS.

**Files / interfaces:** Consumes `docs/build-tasks.json`, `docs/acceptance/E01.md`, `docs/acceptance/E07.md`, `docs/acceptance/artifacts/E01/requirement-assertion-fixture-map.json`; produces/modifies `docs/releases/beta-0.1-evidence-index.json`, `docs/acceptance/artifacts/E01/requirement-assertion-fixture-map.json`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Pin source, trusted base, document, fixture, runtime and policy OIDs separately. Reconcile all 106 planned test names, 26 unnamed cache/output obligations and 17 evaluation invariant rows with assertion bodies; an alternative test name is acceptable only with exact assertion equivalence.
- [ ] **Step 2:** Classify prior evidence as reusable or stale by affected paths/contracts, and list missing, failed, not_run and disputed obligations. Retain historical artifacts; do not import uncommitted local files into a release candidate.
- [ ] **Step 3:** Assign every gap to an existing card or this release queue. Record raw output, commands, input digests, exit codes and adverse expectations; no count-based completeness claim.

**Exit evidence:** Every in-scope obligation has an owner and assertion/fixture mapping; current gaps are visible. Historical suite candidate e4010efcb22e2c576b84c5f4aae77c03d1ddca24 is not current-candidate acceptance.

### BR-03: Complete ingestion, offline, output and recovery boundaries

**Owner:** Kernel boundary implementer. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-02; existing cards: E01-T9-RECORDS, E01-T9-OUTPUT.

**Files / interfaces:** Consumes `docs/evaluation.md`, `docs/security-architecture.md`, `docs/superpowers/plans/2026-10-03-review-kernel.md`; produces/modifies `tests/fixtures/e01/boundaries/`, `tests/fixtures/e01/output/`, `docs/acceptance/artifacts/E01/boundaries/`, `docs/acceptance/artifacts/E01/output/`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Complete missing strict record, immutable Git comparison, source-span, scope receipt, process authority and malicious path/presentation assertions from BR-02. Add a meaningful failing regression before each reproduced defect fix.
- [ ] **Step 2:** Exercise every advertised JSON/Markdown/SARIF format at exact limits and over limits, partial timeouts, closed pipes, backpressure and reserved failure rendering. Confirm incomplete required scope exits 2 with omissions visible; full reports preserve exit semantics 0/1/2/3.
- [ ] **Step 3:** Deny all socket/DNS paths during an end-to-end source-CLI offline review; reject ambient startup/Git config and lazy fetch; preserve bounded unavailable diagnostics. Save focused raw outputs, then assigned development-suite output using PYTHONPATH=src python3.12 -m unittest discover -s tests -v. Repeat these checks on exact released artifact bytes under BR-10; source behavior evidence precedes artifact production.

**Exit evidence:** All mapped boundary/output obligations passed on the pinned candidate; no hidden network calls or reviewed-target execution; raw evidence retained.

### BR-04: Complete trusted-cache mutation and replay equivalence

**Owner:** Cache/kernel implementer. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-02; existing cards: E01-T9-CACHE.

**Files / interfaces:** Consumes `docs/mathematical-core.md`, `docs/evaluation.md`, `tests/test_cache.py`, `tests/test_kernel.py`; produces/modifies `tests/fixtures/e01/cache-mutations/`, `docs/acceptance/artifacts/E01/cache/`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Implement fixtures for completed clean/warm/corrupt/absent cache runs, interrupted writes, component/runtime/schema changes, foreign/shared/symlink entries, added/deleted imports and missing-module recovery.
- [ ] **Step 2:** Compare full completed canonical bytes, coverage, diagnostics, delta classifications and receipt identities across edit sequences; repeat identical logical inputs for byte determinism. Report cold-partial/warm-complete separately and require a complete clean replay before asserting equivalence.
- [ ] **Step 3:** Run PYTHONPATH=src python3.12 -m unittest tests.test_cache tests.test_kernel -v; save full fixture-specific equality and refusal evidence, not just a finding count.

**Exit evidence:** Required mutation/replay and trust-admission assertions passed; stale or untrusted facts are misses; partial runs retain truthful receipts.

### BR-05: Pin advisory rule corpus and independent local user flows

**Owner:** Fixture owner and independent label/user-flow reviewer. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-02; existing cards: E01-T9-CORPUS.

**Files / interfaces:** Consumes `docs/evaluation.md`, `docs/superpowers/specs/2026-10-03-pullraptor-design.md`, `tests/test_rules.py`; produces/modifies `tests/fixtures/e01/corpus/manifest.json`, `tests/fixtures/e01/e2e/`, `docs/acceptance/artifacts/E01/corpus/`, `docs/acceptance/artifacts/E01/user-flows/`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Pin licensed immutable fixtures: at least 10 positive and 10 counterexample/ambiguous cases for each PY001–PY003, including aliases, shadowing, reassignment, nested scopes, conditional re-raise and intentional patterns.
- [ ] **Step 2:** Have an independent reviewer check labels and claim boundaries; disputes remain unresolved. Validate source-CLI review exact base-head/display actionable spans and coverage/repeat after changes/recover missing input flows; include renamed/deleted/Unicode paths and partial coverage. Installation and repeated independent user flows on built artifacts are owned by BR-10, after BR-09.
- [ ] **Step 3:** Run PYTHONPATH=src python3.12 -m unittest tests.test_rules tests.test_cli tests.test_render -v plus pinned user-flow commands. Initial rules stay advisory; no accuracy or default defect-blocking claim without the separate held-out study gate.

**Exit evidence:** Full initial corpus and user-flow receipts passed for beta scope; correctness labels and usefulness observations remain distinct.

### BR-06: Measure the exact benchmark and complexity budgets

**Owner:** Benchmark/platform owner. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-02; existing cards: E01-T9-BENCH.

**Files / interfaces:** Consumes `Master-Plan.md`, `docs/evaluation.md`; produces/modifies `tests/fixtures/e01/benchmark/manifest.json`, `scripts/e01_benchmark.py`, `docs/acceptance/artifacts/E01/benchmark/`, `docs/acceptance/artifacts/E01/runtime-dependency-size-inventory.json`, `docs/acceptance/artifacts/E01/benchmark/real-repositories.json`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Create the specified pinned 10,000-file / 128-MiB fixture: at most 200 Python source files, 20 changed Python files and 2,000 changed lines. Document generator, fixture identities and a 2-vCPU/4-GiB Linux runner.
- [ ] **Step 2:** Measure at least 30 cold and 30 warm repetitions with Python/Git/tool/policy versions and RSS method: p95 cold <=30 seconds, warm <=5 seconds, peak RSS <=512 MiB. Measure deeply nested/adverse inputs separately. Also measure pinned, licensed real-repository base/head pairs, recording language/rule/scope, completion, cold/warm latency, peak RSS and raw receipts separately from the synthetic and adverse fixtures; all three measurement classes are required for BR-07 review.
- [ ] **Step 3:** Inventory kernel versus adapters, dependencies, installed bytes, interpreter/Git/image sizes separately. Review E01 3,000 nonblank/noncomment production-line and 15-module targets; record measured exception decisions rather than compressing validation. The two-file micro benchmark cannot satisfy this task.

**Exit evidence:** Raw measurements meet declared budgets, or a measured scope/cost exception is explicitly approved and limits revised before acceptance; no unmeasured latency claim.

### BR-07: Independently accept E01 for the beta scope

**Owner:** Independent acceptance reviewer. **Mode:** verify. **Status:** pending.

**Prerequisites:** BR-03, BR-04, BR-05, BR-06; existing cards: E01-T9-ACCEPT.

**Files / interfaces:** Consumes `docs/acceptance/E01.md`, `docs/releases/beta-0.1-evidence-index.json`, `docs/personas/reviewer.md`; produces/modifies `docs/acceptance/E01.md`, `docs/acceptance/artifacts/E01/independent-review.md`.

**Operation gate:** Complete BR-03–06 evidence and independent reviewer assignment.

- [ ] **Step 1:** Review all E01-A1/A2/A3 obligations against raw candidate-specific artifacts, adverse behavior, mathematical contract and complete requested user flows; independently reproduce consequential results in the assigned environment.
- [ ] **Step 2:** Reject count-only, placeholder, stale, self-issued or wrong-fixture evidence; record passed/failed/not_run/stale and independent accepted/rejected/pending decision with reviewer and date.
- [ ] **Step 3:** Route concrete failures back to BR-03/04/05/06, fix and recollect affected evidence. Promote only the accepted scope; leave broader capability gates visible.

**Exit evidence:** All E01 beta-required criteria passed with a separate independent acceptance decision; no unresolved critical trust regression.

### BR-08: Pin build dependencies and contain every shipped entry point

**Owner:** Release/dependency owner. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-01, BR-02; existing cards: E07-D01, E07-T1-INVENTORY.

**Files / interfaces:** Consumes `pyproject.toml`, `src/pullraptor/__init__.py`, `docs/dependencies/E07.json`, `Dockerfile`, `release/install_matrix.json`, `docs/releases/beta-0.1-capability-gates.json`; produces/modifies `docs/dependencies/E07.json`, `release/install_matrix.json`, `tests/test_release_provenance.py`, `docs/releases/beta-0.1-entrypoints.json`, `pyproject.toml`, `src/pullraptor/__init__.py`, `src/pullraptor/__main__.py`, `src/pullraptor/publisher.py`, `src/pullraptor/mcp_server.py`, `src/pullraptor/kernel.py`, `tests/test_beta_entrypoints.py`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Inventory exact build-tool wheels, direct/transitive dependencies, binaries, licenses/notices, hashes, redistribution terms and platform requirements. Build a reviewed offline wheelhouse; no floating setuptools>=61.0 or unknown digest is release evidence.
- [ ] **Step 2:** Implement the approved BR-01 version consistently in package/runtime/manifests and any included client metadata. Enumerate console scripts, CLI flags, imports and enabled rules in the actual artifact.
- [ ] **Step 3:** For every shipped interface, inventory its owned acceptance criteria and permitted candidate verification operations. Verify excluded interfaces are absent or clearly refuse without source transfer, writes, target execution or unsupported claims. Included interfaces may remain acceptance-pending during bounded candidate construction; unaccepted activation/target execution/remote operations remain denied. CLI staged/workdir consumes E02-A1; publisher consumes E02; MCP consumes E08; SECRET/security consumes scoped E05 evidence. BR-14, not candidate construction, requires final independent capability admission.
- [ ] **Step 4:** Resolve every enabled conditional_requires row in capability-gates.json, recording pending, failed, stale or not_run admission and its evidence owner without promoting readiness. Do not block candidate construction on its own later build/install acceptance. Construct and verify only within the assigned bounded mode; preserve separate network/isolation/activation gates. BR-14 rejects any included capability still unaccepted; unadvertised executable commands cannot bypass this gate.

**Exit evidence:** Exact license/build/runtime inventory and tested excluded-entrypoint containment; all included interfaces have owned pending admission records. Zero third-party runtime packages in deterministic kernel. Construction prerequisites are resolved; final artifact/capability acceptance is consumed at BR-14, not BR-08.

### BR-09: Produce two clean reproducible artifacts with independently verified origin

**Owner:** Trusted build/provenance owner. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-07, BR-08; existing cards: E07-T2-VERIFY, E07-T2-BUILD.

**Files / interfaces:** Consumes `release/build.py`, `src/pullraptor/release_provenance.py`, `release/manifest.schema.json`, `docs/dependencies/E07.json`; produces/modifies `docs/acceptance/artifacts/E07/builds/`, `docs/acceptance/artifacts/E07/provenance/`, `.github/workflows/release-candidate.yml`, `release/build.py`, `src/pullraptor/release_provenance.py`, `release/manifest.schema.json`, `tests/test_release_provenance.py`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Complete the candidate builder using a reviewed committed source tree and pinned offline tools; reject dirty/untracked substitutions, explicit source OID/tree mismatch, leftover staging wheels and environment-only self-attested origin.
- [ ] **Step 2:** Run PYTHONPATH=src python3.12 -m unittest tests.test_release_provenance -v and two separately clean trusted builds from the identical candidate. Save commands, logs, artifact bytes/sizes/digests and externally acquired build-origin receipts.
- [ ] **Step 3:** Compare distributable bytes from both builds; normalize permitted build metadata explicitly before the comparison, not analyzer reports. Verify actual bytes, trusted repository/workflow/run/source and tampering/wrong-origin refusal. For an included container, pin base image digest and record separate image reproducibility, inventory and credential/egress requirements.

**Exit evidence:** Reproducibility and independent origin/byte verification passed for every included artifact; a candidate self-check or digest alone is insufficient.

### BR-10: Verify real clean installation and source/artifact parity per platform

**Owner:** Installation/platform owners. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-09; existing cards: E07-T3-INSTALL.

**Files / interfaces:** Consumes `release/install_matrix.json`, `tests/test_installed_artifacts.py`, `docs/releases/beta-0.1-scope.json`; produces/modifies `docs/acceptance/artifacts/E07/install/`, `release/install_matrix.json`, `tests/test_installed_artifacts.py`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Run PYTHONPATH=src python3.12 -m unittest tests.test_installed_artifacts -v and actual fresh-platform installation of BR-09 artifact bytes. Deny network for offline cases; remove source checkout/PYTHONPATH access. Mocked wheel/report or local fixture import alone cannot pass installation.
- [ ] **Step 2:** Run source and installed analyzers on the same licensed base/head fixture with advisory findings and a required coverage gap; compare completed canonical bytes and independently check partial receipts/exit codes. Exercise all advertised output formats and entrypoints on each admitted runtime/platform. Repeat BR-03 socket/DNS-denied complete review and BR-05 independently reviewed local user flows against these exact installed artifact bytes.
- [ ] **Step 3:** Measure core installed artifact <=5 MiB, startup/RSS and all declared budgets; record interpreter/Git/image separately. Verify failed/interrupted first installation leaves clean or recoverable state and uninstall removes application/credential remnants. Reject zero/fake revision receipts. Container parity is required if advertised; unsupported platforms stay excluded.

**Exit evidence:** Real clean installs, complete/partial report semantics, footprint and first-install recovery passed for each included profile; profile support derives from saved receipts.

### BR-11: Prepare truthful customer documentation and release support

**Owner:** Documentation/release owner. **Mode:** prepare/verify. **Status:** pending.

**Prerequisites:** BR-01, BR-08, BR-10; existing cards: release coordination task. Draft preparation may begin after BR-01, BR-08; completion still requires all predecessors.

**Files / interfaces:** Consumes `README.md`, `docs/evaluation.md`, `docs/releases/beta-0.1-scope.json`; produces/modifies `README.md`, `CHANGELOG.md`, `docs/install.md`, `docs/releases/beta-0.1-notes.md`, `docs/releases/beta-0.1-support.md`, `docs/releases/beta-0.1-recovery-runbook.md`, `docs/releases/beta-0.1-recovery-rehearsal.json`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Write install-from-artifact, prerequisites, offline setup, exact Git revision review, coverage/exit-code interpretation, cache ownership, uninstall and first-install recovery instructions. Include advisories and known exclusions; no accuracy, enterprise or hostile-isolation claim without evidence.
- [ ] **Step 2:** Include artifact provenance verification instructions, license notices, support/reporting channel, privacy/source-transfer defaults and deprecation/report-schema compatibility policy. Release notes map every claim to acceptance evidence and list unresolved nonblocking limitations.
- [ ] **Step 3:** Have a reviewer execute documentation commands against the final artifacts in BR-10; correct examples and version/profile mismatches. Recommend no automatic merge or target-code execution.
- [ ] **Step 4:** Before readiness/publication, rehearse partial upload, ambiguous upload response and defective-version quarantine/withdrawal in an independently reviewed disposable release-channel fixture, preserving original bytes/digests/evidence. Save recovery receipts and support/operator runbook; corrected bytes require a new version. This rehearsal does not authorize live withdrawal or notifications.

**Exit evidence:** Customer can install and complete the documented beta flow without cloning PullRaptor; every advertised claim has scoped acceptance evidence. Final command verification consumes BR-10; documentation drafting can proceed after preparation_requires. Disposable recovery rehearsal passed before BR-14 readiness.

### BR-12: Clear candidate regressions and independent release risk review

**Owner:** Development verification owner and independent boundary reviewer. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-07, BR-09, BR-10, BR-11; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/security-architecture.md`, `docs/mathematical-core.md`, `docs/personas/reviewer.md`, `docs/releases/beta-0.1-entrypoints.json`; produces/modifies `docs/releases/beta-0.1-regressions.md`, `docs/releases/beta-0.1-risk-review.md`.

**Operation gate:** development verification assignment; explicit sanitized Python 3.12 environment and inert reviewed fixtures.

- [ ] **Step 1:** Assign development verification on the exact candidate with pinned Python 3.12 and sanitized inert fixtures; run PYTHONPATH=src python3.12 -m unittest discover -s tests -v and the trusted-base CI/publication-trust checks. Classify every skip/failure against beta claims.
- [ ] **Step 2:** Independently inspect source-to-policy, subprocess, cache, artifact-origin and shipped command boundaries, report rendering and dependency licenses; add meaningful reproductions for concrete release-blocking defects.
- [ ] **Step 3:** Resolve all in-scope failures and critical trust regressions; fix through scoped PRs, re-pin candidate and rerun affected evidence. Green CI remains regression evidence, separate from E01/E07 acceptance.

**Exit evidence:** All required candidate checks passed and independent review has no unresolved release-blocking issue; exclusions cannot erase required evidence.

### BR-13: Independently accept included E07 distribution scope

**Owner:** Independent distribution acceptance reviewer. **Mode:** verify. **Status:** pending.

**Prerequisites:** BR-09, BR-10, BR-11, BR-12; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/acceptance/E07.md`, `docs/releases/beta-0.1-scope.json`, `docs/acceptance/artifacts/E07/`; produces/modifies `docs/acceptance/E07.md`, `docs/acceptance/artifacts/E07/independent-review.md`.

**Operation gate:** Independent reviewer and complete in-scope distribution evidence.

- [ ] **Step 1:** Assess E07-A1/A2/A3 for included artifacts/profiles using inventory, two-build origins, actual installs, report parity, documentation and first-install receipts; do not infer acceptance from helper tests.
- [ ] **Step 2:** Record a separate accepted/rejected/pending beta-subset decision, reviewer, candidate and remaining full-package obligations. A wheel-only first beta cannot mark whole E07 accepted if container or prior-artifact update/rollback remains unrun.
- [ ] **Step 3:** Keep update/rollback not_run when no independently accepted prior artifact exists; exclude that promise for the first beta and assign BR-18 before any later update/rollback claim.

**Exit evidence:** Independent distribution subset accepted for every beta artifact/profile; full E07 retains partial/acceptance-pending status for outstanding scope.

### BR-14: Freeze exact release candidate and assemble readiness record

**Owner:** Coordinator/release evidence owner. **Mode:** verify. **Status:** pending.

**Prerequisites:** BR-07, BR-12, BR-13; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/releases/beta-0.1-scope.json`, `docs/acceptance/E01.md`, `docs/acceptance/E07.md`, `docs/releases/beta-0.1-capability-gates.json`, `docs/releases/beta-0.1-recovery-rehearsal.json`, `docs/releases/beta-0.1-recovery-runbook.md`; produces/modifies `docs/acceptance/releases/beta-0.1.md`, `docs/releases/beta-0.1-release-manifest.json`, `Master-Plan.md`.

**Operation gate:** All beta-required prior tasks complete; no critical unresolved issue.

- [ ] **Step 1:** Freeze reviewed source commit, trusted base, artifact bytes, build origins, scope/policy/rule/report/runtime/client versions and all evidence digests. Candidate acceptance records may live at a separate immutable evidence commit; avoid a circular requirement to rebuild source solely to embed its own acceptance record.
- [ ] **Step 2:** Audit F01–F32 and delivery amendments as included-and-accepted, excluded or deferred with exact ownership. Validate all required evidence fresh; source/packaging/policy/runtime/artifact changes trigger affected recollection and independent review. Require the BR-11 prepublication recovery rehearsal receipt and every included conditional capability decision; refusal cases must cover enabled publisher/MCP/SECRET scopes with missing or stale evidence.
- [ ] **Step 3:** Record readiness decision, acceptance reviewer identities, artifacts and known limitations. Mark ready_for_release only when BR-01–13 passed for frozen scope. Preserve readiness, publication authorization and released status as distinct fields; set a forecast only from remaining owner estimates and confirmed environment availability.
- [ ] **Step 4:** Evaluate every enabled conditional_requires row against the confirmed capability-gates.json: missing, failed, not_run, stale, rejected, wrong-scope or self-accepted evidence blocks admission/readiness. An excluded interface must be demonstrably absent or disabled; prose exclusion alone is insufficient. Keep unsupported package scope pending.

**Exit evidence:** Complete immutable release dossier supports ready_for_release; no date promised while missing reviewer/environment/evidence blocks remain.

### BR-15: Record maintainer go/no-go and external publication authorization

**Owner:** Human release maintainer. **Mode:** release decision. **Status:** pending.

**Prerequisites:** BR-14; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/acceptance/releases/beta-0.1.md`, `docs/releases/beta-0.1-release-manifest.json`; produces/modifies `docs/releases/beta-0.1-publication-decision.md`.

**Operation gate:** Explicit human release publication authorization required at this operation.

- [ ] **Step 1:** Present the exact accepted source, artifact digests, support scope, release notes, licenses, known limitations and verified release channel to the maintainer.
- [ ] **Step 2:** Record go/no-go, tag/package version, destinations, approved publisher identity and credential boundary. Verify the tag will point to the independently reviewed candidate; refuse changed source or artifact bytes.
- [ ] **Step 3:** Prepare final release assets and commands without publishing. A planning request or independent acceptance decision alone cannot authorize an external release.

**Exit evidence:** Explicit maintainer go decision and publication authorization for exact candidate/assets/destinations, or a documented no-go returning to owned tasks.

### BR-16: Publish immutable beta artifacts through trusted release workflow

**Owner:** Authorized publication operator. **Mode:** release. **Status:** pending.

**Prerequisites:** BR-15; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/releases/beta-0.1-publication-decision.md`, `docs/releases/beta-0.1-release-manifest.json`, `docs/releases/beta-0.1-notes.md`; produces/modifies `docs/releases/beta-0.1-publication-receipt.json`.

**Operation gate:** BR-15 exact publication authorization; trusted workflow and scoped publisher identity.

- [ ] **Step 1:** After approved task PRs merge through trusted-base CI, publish the approved candidate tag, prerelease assets, checksums, inventory/notices and provenance using narrowly scoped release identity. If channel requires signing/attestation, pin signer and verifier and validate both before upload.
- [ ] **Step 2:** Use idempotent reconciliation for partial upload or ambiguous response; never overwrite a published version with different bytes. Verify tag/asset repository, version, source OID and downloaded bytes against BR-14.
- [ ] **Step 3:** Save publication command, operator/run identity, URLs, digest/size, timestamp and result; keep upload failure visible and do not call the beta released until BR-17 succeeds.

**Exit evidence:** Approved immutable assets published and origin-bound receipts saved; no credential handed to analysis workers.

### BR-17: Verify customer download and release state; exercise withdrawal recovery

**Owner:** Release verification/support owner. **Mode:** verify/release record. **Status:** pending.

**Prerequisites:** BR-16; existing cards: release coordination task.

**Files / interfaces:** Consumes `docs/releases/beta-0.1-publication-receipt.json`, `docs/acceptance/releases/beta-0.1.md`, `docs/releases/beta-0.1-support.md`; produces/modifies `docs/releases/beta-0.1-post-publication.md`, `docs/acceptance/releases/beta-0.1.md`, `Master-Plan.md`.

**Operation gate:** Read-only public verification; live withdrawal or user notifications need explicit authorization.

- [ ] **Step 1:** Download from the actual release channel, verify independent provenance/digests and rerun clean install/offline review/coverage/user-flow smoke checks with no source checkout.
- [ ] **Step 2:** Exercise predeclared failed-release recovery without silently replacing bytes: quarantine/withdraw defective version, notify through approved channel, preserve evidence and schedule a new patch version. Consume the successful prepublication BR-11 rehearsal and runbook before using any separately authorized live withdrawal.
- [ ] **Step 3:** Record actual published version/date/support profiles and update Master-Plan only from receipts. A failed public install blocks released/verified status and returns to the responsible task.

**Exit evidence:** Actual customer-path release verified, support/recovery owner active, release record and Master Plan reflect observed state.

### BR-18: Validate patch-beta updates and rollback against accepted prior artifact

**Owner:** Maintenance/release owner. **Mode:** implement/verify. **Status:** pending.

**Prerequisites:** BR-17; existing cards: E07-T3-INSTALL.

**Files / interfaces:** Consumes `docs/acceptance/releases/beta-0.1.md`, `tests/test_installed_artifacts.py`; produces/modifies `docs/releases/beta-0.1-maintenance.md`, `docs/acceptance/artifacts/E07/install/`.

**Operation gate:** Conditional: subsequent beta/update/rollback claim; not a first-beta blocker.

- [ ] **Step 1:** Before a subsequent beta or update/rollback promise, use the independently accepted initial artifact as prior-version fixture; test update, interrupted update, rollback and report preservation.
- [ ] **Step 2:** Run PYTHONPATH=src python3.12 -m unittest tests.test_installed_artifacts -v and actual installed prior/new-version user flows per supported profile. Revalidate source/artifact evidence for each patch candidate.
- [ ] **Step 3:** Publish changed bytes under a new prerelease version only after BR-14–17 gates repeat; record compatibility changes and retained limitations.

**Exit evidence:** Patch-release update/rollback evidence accepted for the claimed profiles; never fabricate prior acceptance.

## Handoff, scheduling and completion

The coordinator dispatches BR-01/02 first; boundary/cache/corpus/benchmark tasks can then receive independent assignments. BR-08 inventory/containment and BR-11 draft docs can proceed before E01 acceptance; actual artifact acceptance consumes it. The critical chain is E01 gaps → independent E01 acceptance → trusted artifact builds → real install → regression/risk review → independent distribution decision → frozen release dossier → human publication decision → publication → downloaded-customer verification. No calendar commitment exists yet. At dispatch record owners, remaining work estimates, environment availability and review windows; publish an evidence-based forecast only after those inputs exist.

For BR-14 review, check every task requirement and every included capability against raw evidence; records created by this planning task never count as product acceptance. The reviewer must be independent of implementation and cannot shrink scope to obtain a green decision. A release deadline cannot override a failed trust boundary. No full roadmap package is accepted by a beta subset decision.
