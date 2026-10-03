# PullRaptor mathematical core

Status: proposed algorithms and contracts. Mathematics should reduce ambiguity and implementation work. It does not turn a partial model of arbitrary code into a proof of correctness.

## 1. Review as a differential transformation

Let B and H be immutable baseline and head snapshots, R a pinned rule/model set, C trusted configuration, and V the toolchain versions. Define:

```text
Review(B, H, R, C, V) -> (findings, evidence, coverage, diagnostics)
```

For rule results F_R, candidate newly detected obligations are:

```text
N = keys(F_R(H)) \ keys(align(F_R(B)))
for each matched obligation o:
  evidence_delta(o) = E_H(o) \ transport(E_B(match(o)))
```

`align` is a partial mapping of root-cause obligations, not a comparison of rendered prose or line numbers. An identity uses rule/version, qualified symbol, obligation discriminator and supported occurrence mapping. E contains modeled witness facts, including source/guard/path obligations. `transport` requires reliable baseline/head mapping and comparable rule/model versions; otherwise the delta is unknown. A separate witness digest detects changed evidence. A new caller path to an existing sink is new evidence and must not disappear through sink-level deduplication. Return both newly detected obligations and evidence deltas on persisting obligations; subtraction of finding IDs alone is insufficient.

Detection delta is not causation. Parsing failure at B, changed rules, ambiguous renames, or unknown alignment prevent an “introduced” assertion. Removal from F_R can mean a rule missed something, scope changed, or a symbol moved. It is not independently proof of repair.

E01 recomputes findings from compact parsed facts for both revisions. Initial incremental optimization reuses parsing only; it does not skip rule evaluation based on a guessed impact cone. This sacrifices some speed for a simpler equivalence argument.

## 2. Dependency closure and bounded impact

Use small adjacency maps. In the directed dependency graph, `u -> v` means u depends on v under a declared relation, such as a supported import or resolved call. Different edge kinds remain distinct; an import graph is not a dataflow graph.

Let D be changed/deleted/new nodes. Later semantic invalidation uses both graphs:

```text
G = G_B union G_H
I_0 = D
I_(k+1) = I_k union predecessors_G(I_k)
I = least fixed point of that iteration
```

A queue traversal is O(|V| + |E|). Preserve old edges so deleting an imported symbol invalidates its consumers. Cycles terminate through a visited set; no graph database or matrix library is needed.

Also invalidate resolution lookup dependencies: a previously absent module may appear, a package boundary may change, or an import path configuration may change without an old resolved edge. Either record successful and failed lookup read sets plus the directory/module search domain, or conservatively redo all resolution. E01 chooses full resolution recomputation.

Known/resolved and possible edges are analysis categories, not proof of executed behavior. A syntactically resolved call may lie in an infeasible branch. External calls, dynamic dispatch, reflection, generated code, runtime imports and framework injection create unknown boundaries.

Only a sound over-approximation for an explicitly bounded model can justify excluding unreachable nodes in that model. Without such a completeness argument, “no path found” is unknown and cannot suppress a security finding. Traversal limits produce partial coverage, never a negative safety fact.

## 3. Finite dataflow, later than E01

For taint hazards T, use the finite lattice P(T), subset order, union join, and monotone transfer functions:

```text
in(n)  = union(out(p) for p in predecessors(n))
out(n) = transfer_n(in(n))
```

Worklist iteration reaches a finite fixed point. Transfer summaries must state their input/output correspondence, alias handling and unsupported behavior. Unknown calls conservatively propagate relevant hazards and attach an unknown-boundary record. Sanitizers remove only a modeled hazard in its valid context; escaping SQL cannot discharge shell or filesystem hazards.

Store predecessor witnesses during propagation. A shortest model path is an understandable explanation, not an executable exploit. Path feasibility, deployment exposure and exploitability are separate evidence dimensions. Reproducing a failing input strengthens the claim but requires the isolated runner.

Authorization is a **must-analysis**, not taint reachability. Facts identify subject, action, resource, and relevant state:

```text
A_in(n)  = intersection(A_out(p) for p in all may-feasible modeled predecessors(n))
A_out(n) = (A_in(n) \ Kill(n)) union Gen(n)
required(n) subset_of A_in(n)
```

Initialize entry with explicitly declared preconditions; initialize non-entry nodes to the finite fact universe and iterate downward appropriately. Include all predecessors in the over-approximate CFG unless infeasibility is established within the bounded model; unknown feasibility remains included. Generate a fact only on a successful authorization-check branch. Kill it after subject/resource reassignment, state invalidation, or an unsupported operation that may change the obligation. An unknown branch cannot add a must fact. Disconnected nodes are not evidence that runtime entry is impossible when the entry model is incomplete.

Dominance is necessary in some models but insufficient: checking the wrong resource, failing open, or using a stale permission after mutation/concurrency breaks the inference. “Authorization not established by this model” is initially advisory; it is not “request is definitely unauthorized.” These obligations require a real CFG/dataflow adapter and framework models, not token matches.

## 4. Evidence accumulation and reporting

For a precisely worded claim c, represent independent support/refutation availability as:

```text
e(c) = (s, r), where s and r are each 0 or 1
```

| Pair | State | Meaning |
|---|---|---|
| (0, 0) | undetermined | sufficient evidence has not been established |
| (1, 0) | supported | recorded evidence supports this precise claim |
| (0, 1) | refuted | recorded evidence contradicts the claim |
| (1, 1) | conflicted | both survive; human attention or new analysis needed |

Accumulate using componentwise OR. Do not erase counterevidence because a later model repeats the allegation. Different revisions are different claim contexts; evidence from H1 does not automatically support H2. Deduplicate correlated copies and preserve provenance. Support for “uses a shell” does not become support for “has command injection.”

A reportable asserted claim needs fresh revision binding, valid source location, sufficient witness for that claim type, and completed required analysis. A blocker additionally needs a trusted policy mapping and no unresolved conflict. Unknown results can be reported as questions or diagnostics with their uncertainty label. Hashes ensure content identity, not truth, authorship, authorization, or test adequacy.

Use severity, delta class, evidence class and coverage as separate fields. Before calibration, sort with an explicit deterministic tuple; do not multiply invented probabilities to produce a numeric risk score. Blast-radius counts are modeled graph counts, not likelihood or business loss.

## 5. Empirical calibration and selective decisions

Later calibration uses independent held-out labels for a predeclared rule/language/evidence stratum. With x correct findings out of n adjudicated findings, p_hat = x/n, and z = 1.96:

```text
L = (p_hat + z*z/(2*n)
     - z*sqrt(p_hat*(1-p_hat)/n + z*z/(4*n*n)))
    / (1 + z*z/n)
```

This is the lower endpoint of a nominal 95% Wilson interval for precision under sampling assumptions. For n = 0, the bound is unavailable. Small samples, repository clustering, label disputes, and distribution shift prevent a strong guarantee. No detector gets a confidence number from agreement between correlated agents.

A proposed default-blocking gate requires n >= 100 independently adjudicated emitted findings in the applicable stratum and L >= 0.90, plus the deterministic evidence and regression gates. Treat this as a release criterion, not a per-finding 90% correctness probability. For clustered data, use repository-held-out evaluation and a clustered uncertainty analysis; the nominal Wilson number alone is insufficient.

For a reporting threshold tau:

```text
selective_error(tau) = incorrect_reported / total_reported
candidate_coverage(tau) = total_reported / total_candidates
defect_recall = correctly_detected_defects / all_adjudicated_defects
```

Zero denominators are undefined, not zero error. Candidate coverage cannot reveal defects that never became candidates. Record recall using separately constructed defect-positive and defect-negative inputs; do not tune thresholds on the final test set. Human reactions measure utility, not correctness ground truth.

## 6. Context under a budget

Let each context block i have serialized cost c_i, explicit relevance priority w_i, and let M be mandatory witnesses. Select X under:

```text
maximize sum(w_i for i in X)
subject to sum(c_i for i in X) <= B and M subset_of X
```

E03 uses a simple deterministic priority/cost greedy heuristic after mandatory blocks; it does not claim optimal knapsack performance. Ties resolve by stable source ID. If mandatory material exceeds B, split the task or abstain on the claim. Never omit the guard or sanitizer from a security witness merely to fit a prompt.

Use exact serialized byte costs for the byte budget. Without a provider tokenizer, bytes/characters cannot guarantee token cost. Bound requests and requested output separately. Provider usage receipts inform actual cost afterward. Budget exhaustion must be reported independently of absence of findings.

## 7. Cache and receipt algebra

An immutable snapshot manifest includes sorted path/mode/blob entries. Reuse keys include a content digest, exact parser/runtime version, fact schema, rule/model version when relevant, trusted configuration and actual read-set dependencies. JSON encoding is canonical: stable keys and lists, UTF-8, no nonfinite numbers. Git object IDs may be SHA-1 or SHA-256 and are not hardcoded to one length.

E01 caches per-blob parser facts only. Resolution, coverage and rule evaluation are rebuilt each run. Later semantic caches must additionally include successes, lookup misses, module search domains and pinned external advisory/context inputs. An unknown dependency invalidates reuse.

For completed logical analyses with the same requested scope and pinned inputs, the required invariant is:

```text
canonical(Review_incremental(B, H, R, C, V))
== canonical(Review_clean(B, H, R, C, V))
```

Compare findings, locations, witnesses, delta states, coverage and diagnostics; counts alone are inadequate. Cache hit/timing data lives outside canonical output. Corrupt/missing cache is a miss and produces the same semantic result when analysis completes. Wall-time limits can make clean and warm runs complete different amounts of work. Such runs remain explicitly partial and cannot satisfy this invariant until a full clean replay completes. Write an atomic temp file and replace; cap cache size and do not trust executable cache content.

## 8. Patch evidence and monotonic status

For a proposed patch p against H, validation stages are separate predicates:

```text
P0: patch preconditions and allowed paths match H
P1: patch applies without fuzz/conflict
P2: changed source parses under declared adapters
P3: affected review obligations re-evaluated on H+p
P4: configured isolated regression checks ran with recorded results
```

Record each validation predicate separately with `passed`, `failed`, `not_run`, or `stale`, and keep a draft/delivery state. Do not collapse skipped prerequisites into a single “verified” label. `checks_passed` describes configured checks only; `regression_reproduced_and_resolved` additionally requires the relevant baseline failure and corresponding post-patch pass. Passing P1 does not imply P2, and P4 does not prove equivalence or completeness. A blocker clears only after its specific obligation is discharged by fresh evidence, not because unrelated tests pass. A changed head makes an old receipt stale.

No model can promote its own patch from draft to verified. The validator checks actual records. Keep patches scoped and never automatically merge. This gives the mathematics an observable product consequence: users can see exactly which obligation was checked and which was left open.
