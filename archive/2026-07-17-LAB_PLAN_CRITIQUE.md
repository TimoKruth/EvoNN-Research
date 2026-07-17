# Critique of `LAB_PLAN.md`

**Date:** 2026-07-17  
**Reviewed artifact:** `LAB_PLAN.md`  
**Authority used:** `claude-spec/` chapters 00–19, `claudex-spec/19-research-interop.md`, `PROGRAM_CHARTER.md`, and the integrity synthesis in `spec-comparison.html`  
**Purpose:** Identify contradictions, omissions, false-positive exit gates, execution risks, and concrete corrections before `LAB_PLAN.md` is installed as the Lab repository's `CONSOLIDATED_PLAN.md`.

---

## Executive assessment

`LAB_PLAN.md` is a major improvement over the earlier high-level program plan. It restores the normative Phase 0–7 sequence, separates scientific completion (`L-SCI`) from producer interoperability (`I1`), front-loads most of the comparison's integrity fixes, and translates much of `claude-spec` into concrete work packages and verification surfaces.

Its overall architecture is sound and unusually disciplined for a greenfield research platform. In particular, it correctly makes Contenders and Compare precede engine claims, gives evidence and statistics their own phase, treats negative scientific results as legitimate outcomes, preserves engine distinctness, and includes the otherwise easily omitted Phase 7 work.

It is nevertheless **not ready to execute unchanged**. Several defects can cause the implementation to pass a named phase while still violating the specification:

1. The proposed per-WP plan files conflict with the single-active-plan policy.
2. The specification and charter bootstrap is not reproducibly pinned.
3. Phase 0's exit is internally impossible in one respect and falsely passable in others.
4. The budget contract is missing a required field and permits the wrong partial-run semantics.
5. Required contender groups and floor-adequacy rules are incomplete.
6. Linux fallback is planned mainly as export smoke rather than compare-grade execution.
7. Topograph QD work is placed in Phase 2 despite the roadmap explicitly deferring QD extras to Phase 6.
8. Phase 3 collapses distinct statistical and PR decision vocabularies.
9. The transfer campaign can label a `reported_prior` result as a gain without the required `charged_prior` confirmation.
10. The `L-SCI` positive and negative paths lack sufficiently exact decision-grade completion criteria.
11. Interop producer conformance is not tied tightly enough to consumer dossier fields, real runtime-produced artifacts, compatibility semantics, and the I1/I2/I3 authorization boundary.
12. Many WPs are epics rather than coherent TDD-sized work packages, while the proposed mechanism for expanding them creates the planning-policy problem above.

The recommended disposition is:

> **Revise before bootstrap.** Preserve the phase structure and most WPs, but correct the blocking contract/gate errors, replace per-WP active plan files with in-plan or PR-local checklists, pin all governing documents, and make each phase exit machine-verifiable against explicit commands and evidence artifacts.

---

## Severity model

- **Critical:** Can make the project violate a normative contract, authorize an invalid scientific claim, or undermine the execution-plan governance model.
- **High:** Can make a phase pass without satisfying its scientific, portability, or interoperability purpose.
- **Medium:** Significant executability, maintainability, or ambiguity problem that should be corrected during WP expansion.
- **Low:** Terminology, clarity, or documentation improvement.

---

# Critical findings

## C1. Per-WP sub-plan files violate the single-active-plan policy

The plan instructs workers to expand every WP into `docs/plans/YYYY-MM-DD-wp-<id>.md` and says implementation must proceed from those files rather than from the master plan (`LAB_PLAN.md:3-8`).

The governing documentation policy requires exactly one active execution plan, `CONSOLIDATED_PLAN.md`. Branch planning is limited to a short PR checklist or a small section in that plan; competing active plan files are prohibited (`claude-spec/18-engineering-standards.md:35-45`, `claude-spec/18-engineering-standards.md:57-60`).

This is not merely naming. If the generated WP files become the operative instructions, `CONSOLIDATED_PLAN.md` ceases to be the single source of execution truth.

### Required correction

Use one of these compliant patterns:

1. Expand the active WP in a nested section of `CONSOLIDATED_PLAN.md`, replacing the summary temporarily or appending a bounded checklist.
2. Use a short PR/issue checklist that explicitly cites the WP but is not represented as a second project plan.
3. If historical implementation notes are desired, move completed checklists into research logs after the WP closes and mark them non-authoritative.

Add the policy test already anticipated by chapter 18: fail CI if another file declares itself an active execution plan.

---

## C2. Repository bootstrap is not reproducibly tied to its governing specifications

The plan says to copy `claude-spec/` into the new repository "or submodule" it (`LAB_PLAN.md:459-460`). It does not require:

- the upstream repository URL;
- exact source commit;
- specification semantic version;
- tree/content digest;
- update and supersession procedure.

That is incompatible with the provenance promises needed by the Lab export boundary. Consumable artifacts must state the Lab specification version and source commit (`claude-spec/19-product-interop.md:54-68`), while Product import dossiers require the source specification version, commit, and digests (`claudex-spec/19-research-interop.md:21-28`).

The plan also depends on `PROGRAM_CHARTER.md` (`LAB_PLAN.md:425-426`) and on Product-side acceptance semantics, but the bootstrap action mentions only `claude-spec/`. Product acceptance is explicitly governed by `claudex-spec/19-research-interop.md`, not by the Lab chapter or charter (`claudex-spec/19-research-interop.md:12-15`).

### Required correction

At bootstrap, install immutable references to all governing sources:

- `claude-spec/` at an exact commit and declared spec version;
- `PROGRAM_CHARTER.md` at an exact commit;
- `claudex-spec/19-research-interop.md` at an exact commit/version.

Prefer a commit-pinned submodule or subtree. If vendored, add a provenance manifest containing upstream URL, commit, spec version, import date, and tree digest. Define how specification upgrades are reviewed, recorded, and reflected in plan traceability.

---

## C3. Phase 0's exit gate is both internally impossible and falsely passable

Phase 0 creates only Shared and benchmark packages (`LAB_PLAN.md:72-97`) but exits when "contracts import everywhere" (`LAB_PLAN.md:158-160`). At this point Contenders, Compare, and all engines do not yet exist, so "everywhere" cannot be tested. The normative roadmap uses that wording, but an executable plan must establish package skeletons or narrow the claim (`claude-spec/17-roadmap-and-horizons.md:64-75`).

At the same time, the Foundation Integrity Gate includes uninterrupted-versus-resumed equivalence but defers real engine exercise until Phase 2 (`LAB_PLAN.md:147-156`). The phase can therefore report the integrity suite green before a resumable engine exists. Yet the updated Phase 0 gate explicitly includes uninterrupted-versus-resumed equivalence (`claude-spec/17-roadmap-and-horizons.md:69-75`).

### Required correction

Make Phase 0 prove contracts and resume behavior against executable skeletons:

- create minimal package skeletons for Shared, Benchmarks, Contenders, Compare, Prism, Topograph, Stratograph, and Primordia;
- run import-direction policy tests across all skeletons;
- implement a deterministic no-op/reference resumable runner that proves the generic resume contract in Phase 0;
- retain mandatory engine-specific resume equivalence tests when each engine is implemented.

Alternatively, rename the Phase 0 claim to "contracts import in all Phase 0 packages" and explicitly keep the full integrity gate open until the first engine-specific proof. The current wording must not allow a placeholder test to represent completed engine resume integrity.

---

## C4. The budget accounting contract is incorrect

The global field list and WP-0.3 omit `resumed_evaluations` (`LAB_PLAN.md:38-41`, `LAB_PLAN.md:113-116`). Chapter 03 requires both `resumed_from_run_id` and `resumed_evaluations` (`claude-spec/03-budget-and-fairness.md:42-51`).

More seriously, WP-0.3 proposes:

> `actual ≤ declared` unless `partial_run`

That exception is backwards. A partial run may have **less** actual work than declared; partial status does not authorize an overrun. The specification gives no exemption allowing `actual_evaluations > evaluation_count` (`claude-spec/03-budget-and-fairness.md:44-56`).

### Required correction

- Add `resumed_evaluations` everywhere the accounting contract is listed or modeled.
- Require `actual_evaluations <= evaluation_count` for normal and partial runs unless a separately versioned amendment/overrun contract exists.
- Require `partial_run=true` when actual counted work is below the declared envelope because execution stopped early.
- Validate accounting identities and reject negative, inconsistent, or double-counted resumed/cached work.

This correction is required before any fairness or lane claim can be trusted.

---

## C5. A transfer `gain` can be promoted without budget-matched confirmation

The plan correctly defaults early transfer studies to `reported_prior` (`LAB_PLAN.md:347-350`) but allows the campaign to classify and promote `gain` without explicitly requiring replication under `charged_prior` (`LAB_PLAN.md:355-362`).

The specification is unambiguous: `reported_prior` excludes source cost from a direct budget-matched claim, and a budget-matched transfer gain may be claimed only under `charged_prior` (`claude-spec/03-budget-and-fairness.md:107-109`, `claude-spec/11-seeding-and-transfer.md:71-80`).

### Required correction

Separate two outcomes:

- `provisional_gain_reported_prior` — valid research signal, not a budget-matched transfer success;
- `gain` — confirmed under `charged_prior`, with matched pack, budget, seed, backend, and contender context.

The Phase 5 exit may still pass with `regression`, `no_gain`, or `inconclusive`; a positive transfer-success claim must meet the stricter condition.

---

## C6. The positive and negative `L-SCI` paths are not decision-complete

WP-6.6 allows a repeated engine win/tie or an evidence-backed negative conclusion (`LAB_PLAN.md:387-394`). This is directionally correct, but the exact closure rules are insufficient.

### Positive-path gap

The work package does not explicitly require:

- a contender-including cohort;
- the applicable tier's minimum seed gate;
- exclusion of ceiling ties from superiority evidence;
- effect size and confidence intervals;
- an L4 statistical decision label;
- a green artifact-completeness validation.

External performance claims must come from contender-including evidence (`claude-spec/12-evidence-and-statistics.md:137-143`), and promoted claims require the repeated-run and statistical surfaces in chapter 12 (`claude-spec/12-evidence-and-statistics.md:58-93`).

### Negative-path gap

"Either outcome passes" can be read to permit an underpowered, blocked, or incomplete campaign to become the negative scientific conclusion. But `needs_more_runs`, `blocked`, and `inconclusive` are first-class non-decisions (`claude-spec/12-evidence-and-statistics.md:75-82`).

### Required correction

Define a fixed L-SCI evidence matrix before execution.

A **positive** closure requires a promoted contender-including cohort that:

- passes the tier seed gate;
- has a qualified, non-weak floor;
- excludes ceiling ties from superiority evidence;
- reports effect sizes, uncertainty, runtime tradeoffs, and exact claim scope;
- receives a decision-grade label;
- passes `evidence validate --require-artifacts`.

A **negative** closure requires the same predefined coverage and repeated-run completeness, followed by an evidence-backed conclusion that no engine clears the floor on the declared claim surface. `blocked`, `needs_more_runs`, and unresolved coverage gaps keep L-SCI open.

---

# High-severity findings

## H1. Phase 0 portability is below the specified bootstrap bar

WP-0.1 establishes executable Linux Shared checks but leaves the macOS workflow as a stub (`LAB_PLAN.md:99-104`). The Phase 0 roadmap requires both CI lanes (`claude-spec/17-roadmap-and-horizons.md:64-70`), and the portability chapter requires platform-conditional MLX installation plus specific Linux/macOS package lanes (`claude-spec/13-runtime-portability.md:17-21`, `claude-spec/13-runtime-portability.md:45-63`).

### Correction

At Phase 0 exit, require:

- real Linux and macOS workflow execution, not a stub;
- clean Linux installation proving MLX is platform-conditional;
- declared backend-capability manifests for package skeletons;
- exact host/runtime metadata in CI-produced fixture artifacts.

---

## H2. Export contract implementation is incomplete

WP-0.2 omits required result fields such as `task_kind`, memory, and per-benchmark evaluation counts, and names only a manifest writer (`LAB_PLAN.md:105-112`). The standard contract requires `manifest.json`, `results.json`, and `summary.json`, with the complete result surface (`claude-spec/04-telemetry-and-artifacts.md:57-84`).

### Correction

Require strict models and round-trip writers/readers for all three files. Add valid/invalid fixtures covering unsupported/skipped visibility, runtime metadata, budget echo, fairness flags, artifact digests, and schema-version compatibility.

---

## H3. The Foundation Integrity Gate still omits two named integrity obligations

The plan includes RNG streams, resume equivalence, atomic checkpoints, immutable evaluations, read-only export, and measurement/proxy labeling (`LAB_PLAN.md:147-155`). It does not include:

- physical test-label separation;
- a named behavior-level speciation test wherever NEAT terminology is used.

Both are part of the charter/comparison synthesis (`PROGRAM_CHARTER.md:62-70`, `spec-comparison.html:456-468`, `spec-comparison.html:492-497`). The roadmap also states that genuine speciation behavior belongs to the standing integrity bar (`claude-spec/17-roadmap-and-horizons.md:69-75`).

### Correction

Add:

- a capability-boundary test proving protected labels cannot be accessed during search/selection where such datasets are used;
- an engine hook proving speciation materially changes reproduction/survival before any NEAT claim is allowed.

The latter can be activated when Topograph exists, but the gate contract and required test name should be defined in Phase 0.

---

## H4. Canonical run-directory conformance is stated but not verified

The canonical run layout is a global rule (`LAB_PLAN.md:42-44`), but WP-0.7 tests only DuckDB tables, locking, and append-only evaluations (`LAB_PLAN.md:134-136`). Phase 0 has no acceptance test creating and validating the complete workspace required by `claude-spec/01-system-architecture.md:145-163`.

### Correction

Add a `RunWorkspace` constructor/validator and an end-to-end fixture that creates:

- `config.yaml`;
- `metrics.duckdb`;
- `state.json`;
- `summary.json`;
- `report.md`;
- `checkpoints/`;

then rebuilds the report and verifies artifact references without mutating canonical evidence.

---

## H5. Required contender floors omit image and language-modeling groups

WP-1.1 lists tabular and synthetic required pools only (`LAB_PLAN.md:172-176`). Chapter 06 also requires dependency-light image and language-modeling floors: flat-feature MLP/tree baselines and n-gram baselines (`claude-spec/06-contenders.md:11-18`).

This matters once Tier B image and LM packs are introduced; those packs cannot become trusted or decision-grade without a required contender result (`claude-spec/06-contenders.md:32-45`).

### Correction

Implement all four required groups in WP-1.1, even if some are exercised only when their packs arrive. Keep CNN and tiny-transformer pressure optional behind extras as planned.

---

## H6. Benchmark audit checks floor presence but not floor adequacy

WP-1.7 checks that floors are present (`LAB_PLAN.md:201-203`) but does not require the per-benchmark adequacy vocabulary:

- `strong_floor`;
- `acceptable_floor`;
- `weak_floor`;
- `missing_enhanced_pressure`.

A `weak_floor` must block decision-grade promotion (`claude-spec/06-contenders.md:32-45`). The broader admission gate also requires runtime class, cache validation, budget divisibility, repeated runs, and zero blockers (`claude-spec/02-shared-benchmarks.md:157-180`).

### Correction

Make adequacy labels part of the audit schema and enforce `zero blockers` before a pack enters a decision-grade lane.

---

## H7. Compare lane semantics and dashboard requirements are incomplete

WP-1.4 lists positive lane states but omits explicit `exploratory/reference` states and does not prohibit `--no-contenders` cohorts from supporting external-floor claims (`LAB_PLAN.md:186-192`). The specification requires these non-decision states and separates engine-only from contender-including use (`claude-spec/05-compare.md:103-116`, `claude-spec/12-evidence-and-statistics.md:137-143`).

WP-1.6 calls the Evidence Explorer a stub and omits several required surfaces: pairwise seed deltas, recent full-run history, named decision slices, measurement downgrade reasons, and backend/hardware filtering (`LAB_PLAN.md:197-200`). These are normative dashboard functions (`claude-spec/05-compare.md:130-150`, `claude-spec/04-telemetry-and-artifacts.md:123-130`, `claude-spec/13-runtime-portability.md:34-43`).

### Correction

Either complete the Phase 1 dashboard contract or explicitly mark Phase 1 as a reduced bootstrap surface and keep the phase exit below the roadmap's dashboard claim. Prefer completing it because later decision-gate enforcement depends on named slices.

---

## H8. Linux fallback is planned as export smoke, not compare-grade execution

WP-2.10 provides a NumPy-fallback smoke path for the engines' export surface (`LAB_PLAN.md:259-262`). The portability requirement is stronger: each engine needs Linux-capable smoke, regression, and compare-grade small-budget studies under the same packs and contracts (`claude-spec/13-runtime-portability.md:23-32`).

### Correction

For every engine, require a Linux fallback lane that performs a real tiny search/evaluation, resume, report rebuild, symbiosis export, and Compare ingestion. Results must remain classified as fallback/portability evidence and never mix silently with MLX-native cohorts (`claude-spec/13-runtime-portability.md:34-43`).

---

## H9. Topograph QD is scheduled in the wrong phase

WP-2.8 includes novelty archives and a MAP-Elites grid (`LAB_PLAN.md:251-256`). The roadmap defines Phase 2 as full chapter 08 **minus QD extras**, reserving descriptor schema, archive reporting, and the first QD experiment for Phase 6 (`claude-spec/17-roadmap-and-horizons.md:84-86`, `claude-spec/17-roadmap-and-horizons.md:110-115`).

Including partial QD in Phase 2 also creates an incomplete implementation: no shared descriptors, archive reporting, equal-budget control, or promotion gate exists yet.

### Correction

Keep ordinary speciation/novelty mechanisms needed for Topograph identity if they are non-QD search mechanics, but move MAP-Elites and QD archive behavior to WP-6.1/6.2. Make the boundary explicit in the Phase 2 sub-plan.

---

## H10. Topograph's promised non-QD chapter 08 scope is incomplete

Phase 2 claims full chapter 08 minus QD extras, but the listed WPs omit the hardware-aware surfaces: `target_device`, latency/memory/throughput/compileability objectives, and the device-aware topology atlas (`LAB_PLAN.md:239-258`; `claude-spec/08-engine-topograph.md:131-137`).

### Correction

Either add the missing hardware-aware contract and reporting WPs to Phase 2 or narrow the claim from "full ch. 08 minus QD extras" and schedule the remainder explicitly.

---

## H11. Engine telemetry has no explicit acceptance matrix

The plan says L3 fields are propagated but does not enumerate required engine-specific telemetry (`LAB_PLAN.md:219-262`). Chapter 04 requires additional fields for Prism, Topograph, Stratograph, and Primordia (`claude-spec/04-telemetry-and-artifacts.md:40-49`).

### Correction

Add a shared telemetry conformance matrix and per-engine golden tests. Phase exits should fail when mandatory family/archive/inheritance/operator, topology/novelty, hierarchy/reuse, or primitive-bank telemetry is absent.

---

## H12. Phase 2 and Phase 4 exit gates understate output-quality prerequisites

Phase 2's exit names only `tier1_core@64` (`LAB_PLAN.md:264-266`) even though the standing and normative requirement is L3 on both Tier A and the trusted daily lane (`claude-spec/04-telemetry-and-artifacts.md:123-127`).

Phase 4 admits Stratograph and Primordia directly into a Tier B `trusted-extended` cohort without explicitly first proving them at L3 on Tier A and `tier1_core@64` (`LAB_PLAN.md:329-335`).

### Correction

Add explicit prerequisites:

- Prism and Topograph: L3 on Tier A and `tier1_core@64` before Phase 2 closes.
- Stratograph and Primordia: the same L3 gate before their Tier B evidence is considered.
- `trusted-extended`: L4 repeated-seed aggregate, statistical decision label, complete contender floor, and all decision-grade artifacts—not merely L3 per-run output.

---

## H13. Phase 3 collapses distinct decision vocabularies

WP-3.2 uses four conservative labels: `gain`, `no_material_change`, `inconclusive`, and `blocked` (`LAB_PLAN.md:279-282`). The specification distinguishes:

- cohort labels such as `clear_gain`, `likely_gain`, `regression`, and `needs_more_runs`;
- aggregation labels;
- PR advancement categories such as `Tier 1 regression`, `needs more seeds`, `Tier B-only gain`, `regress`, `promote`, and `inconclusive`.

See `claude-spec/12-evidence-and-statistics.md:75-82` and `claude-spec/05-compare.md:180-210`.

### Correction

Model these as separate enums/fields with explicit mappings. Do not compress scientific statistics, grouped summaries, and merge decisions into one label.

---

## H14. Evidence validation and PR enforcement are not machine-enforced enough

The plan creates `evidence validate` and a PR template (`LAB_PLAN.md:275-292`) but does not make `evidence validate --require-artifacts` a mandatory gate before citation. Chapter 12 explicitly requires it (`claude-spec/12-evidence-and-statistics.md:35-50`).

Likewise, the PR template does not include a CI policy check enforcing artifact paths, exact case/run IDs, named dashboard slices, lane states, and exactly one decision category (`claude-spec/05-compare.md:180-210`).

### Correction

Add a policy checker invoked in CI and at Phase 3 exit. It should parse the PR evidence block and validate every cited artifact against the registry.

---

## H15. Statistical implementation omits required tests and diagnostics

WP-3.3 includes effect sizes and bootstrap intervals but omits guarded Wilcoxon/Friedman-style tests (`LAB_PLAN.md:283-287`; `claude-spec/12-evidence-and-statistics.md:67-73`).

The evidence report also omits mandatory diagnostic sections for transfer-proof state, LM flatlines, and first-pass evidence-derived engine roles (`claude-spec/12-evidence-and-statistics.md:95-105`).

Runtime tradeoffs are not explicitly mandatory in each advancement-ready evidence group, even though quality gains must report wall-clock, evaluations/sec, seconds/success, score/sec, and family allocation (`claude-spec/12-evidence-and-statistics.md:145-151`).

### Correction

Add these to the Phase 3 report schema, with explicit `not_applicable` or `insufficient_data` outcomes rather than silent omission.

---

## H16. Phase 4 benchmark admission and engine CLI gates are too vague

WP-4.7 says "presets; audits" without requiring the zero-blocker decision-grade audit (`LAB_PLAN.md:326-328`). The benchmark specification defines exact candidate and decision-grade gates (`claude-spec/02-shared-benchmarks.md:157-180`).

WP-4.8 adds CI scripts but does not explicitly require complete engine CLI conformance and export-contract smoke paths for Stratograph and Primordia (`LAB_PLAN.md:329-331`; `claude-spec/04-telemetry-and-artifacts.md:94-108`).

### Correction

Require the exact audit command, zero blockers, and end-to-end tiny-config tests for evolve/run, resume, inspect, report, benchmark/cache discovery, and symbiosis export.

---

## H17. Primordia artifact semantics are underspecified

WP-4.6 names files but not their required semantic contents or recovery behavior (`LAB_PLAN.md:323-325`). Chapter 10 requires ranked diversity descriptors, benchmark-conditioned seed information, leaders, primitive usage/coverage/failure telemetry, and reconstruction when the primitive-bank view is absent (`claude-spec/10-engine-primordia.md:64-78`).

### Correction

Add strict schemas and reconstruction tests rather than treating file existence as artifact completion.

---

## H18. The native transfer protocol is incomplete

Phase 5 has several gaps:

1. "Native" is not explicitly pinned to Topograph's real MLX runtime (`LAB_PLAN.md:347-362`), although only MLX-native consumption can support a transfer claim (`claude-spec/11-seeding-and-transfer.md:89-99`).
2. The exact validation sequence omits `tier_c_architecture_sensitive@128` (`LAB_PLAN.md:355-359`; `claude-spec/11-seeding-and-transfer.md:110-119`).
3. Identical pack, budget, seed, backend, and contender context across regimes is described but not an automated acceptance rule.
4. The ≥5% relative-improvement template surviving both baselines with clean attribution is not encoded (`claude-spec/11-seeding-and-transfer.md:144-152`).

### Correction

Make Phase 5 emit a machine-validated transfer campaign manifest. Reject unmatched regime matrices. Record full runtime metadata, keep fallback results portability-only, run the exact prescribed sequence, and define the positive-gain bar explicitly.

---

## H19. QD promotion is not operationally defined

WP-6.2 compares a QD branch "vs baseline at equal budget" and promotes if diversity improves without destroying quality (`LAB_PLAN.md:371-375`). It does not define:

- the same-engine QD-disabled control;
- identical packs, seeds, backend, and evaluation policy;
- descriptor definitions and bins;
- diversity improvement threshold;
- allowed quality-loss/non-inferiority margin;
- per-cell improvement and Pareto/diversity views.

The required rollout and reporting surfaces are in `claude-spec/14-quality-diversity-and-multiobjective.md:56-79`.

### Correction

Pre-register the QD experiment and its decision thresholds before running it. Add all required reporting surfaces and require repeated seeds before promotion.

---

## H20. Tier C/D evidence gates remain incomplete

WP-6.4 reproduces Tier C's two clean 512 plus one clean 1024 hardening gate (`LAB_PLAN.md:378-382`) but omits the additional L4 seed requirements: three local-budget and two overnight seeds before decision-grade promotion (`claude-spec/12-evidence-and-statistics.md:58-65`).

The one-seed runtime-envelope probe is not explicitly quarantined as exploratory and backend/host-locked. Tier D is called an admitted broad lane but the plan does not explicitly require its separate leaderboard and prohibit broader claims until three clean repeated runs (`claude-spec/02-shared-benchmarks.md:137-141`).

### Correction

State that benchmark admission gates and statistical promotion gates are cumulative, not alternatives. Mark envelope probes exploratory and non-promotable.

---

## H21. Portfolio decisions do not constrain the evidence cohort type

WP-6.5 requires registry links but does not require engine-only cohorts for portfolio status decisions (`LAB_PLAN.md:383-386`). The evidence rules explicitly reserve engine-only evidence for specialization/portfolio balance and contender-including evidence for external claims (`claude-spec/12-evidence-and-statistics.md:137-143`).

### Correction

Encode the allowed evidence cohort type in the status-change validator.

---

## H22. Phase 7 measurement and acceptance gates are too weak

The performance bundle omits parts of the mandatory measurement set: candidates evaluated, valid/invalid ratio, seconds/success, backend vs orchestration time, per-benchmark latency, peak memory, family allocation, quality delta, and contender-floor margin delta (`LAB_PLAN.md:402-405`; `claude-spec/13-runtime-portability.md:82-87`).

The optimization slices do not require the prescribed Tier A 16/64, Tier B 96/384, conditional Tier C, seed, backend, and host matrix (`LAB_PLAN.md:406-408`).

"Observatory browsable" is below the Observatory acceptance surface: scanner cadence, JSON-only ingestion, required pages, explanatory banners, filtering, variance, and decision-grade labeling are not tested (`LAB_PLAN.md:409-419`; `claude-spec/15-observability-and-dashboards.md:20-78`).

Finally, two weeks of trend rows is a time-based rather than evidence-based automation gate. Cadence, minimum successful/failed row count, and improvement/regression/no-change classification are unspecified (`LAB_PLAN.md:412-419`).

### Correction

Replace Phase 7's exit with explicit conformance tests and minimum observation counts. Time may be a supporting condition but not the only automation criterion.

---

## H23. Interop versioning and producer artifacts do not yet prove consumer usability

WP-I.1 mentions semantic versions and changelogs but does not require:

- append-only registry history;
- immutable field meaning;
- major bumps for breaking changes;
- compatibility ranges;
- supersession metadata used by Product staleness rules.

See `LAB_PLAN.md:428-429`, `claude-spec/19-product-interop.md:54-68`, and `claudex-spec/19-research-interop.md:148-176`.

WP-I.2's mechanism dossier does not explicitly include all producer information needed to populate a Product import dossier: source envelope, claim magnitude/scope, evidence labels, case/run IDs, risks, license, spec version, commit, and digests (`LAB_PLAN.md:430-432`; `claudex-spec/19-research-interop.md:114-130`).

One negative-result example is not enough; negative results and scope limits must be schema-level fields where applicable.

### Correction

Define a shared provenance/source envelope and make dossier completeness machine-validated.

---

## H24. I1 can close without representative real artifacts

WP-I.3 produces fixtures and WP-I.4 validates published artifact classes (`LAB_PLAN.md:433-438`), but the plan does not explicitly require runtime-produced examples from every Lab export surface. The charter correctly distinguishes fixtures from real artifacts (`PROGRAM_CHARTER.md:147-151`).

### Correction

Gate I1 on both:

- fixture conformance, including invalid/corrupt/version cases;
- at least one real runtime-produced artifact from each of the five Lab export surfaces.

Publish a fixture manifest specifying expected accept/reject/stale behavior and expected loss labels for every old-version fixture.

---

## H25. The I1/I2/I3 authorization boundary is not a standing execution rule

The plan targets I1 but does not explicitly state that producer conformance alone cannot authorize real Lab-derived Product influence (`LAB_PLAN.md:10-13`, `LAB_PLAN.md:423-438`). The charter says real imports require both I1 and I2 and are recorded under I3 (`PROGRAM_CHARTER.md:17-30`, `PROGRAM_CHARTER.md:168-183`).

### Correction

Add a standing rule:

> I1 proves only Lab publishing readiness. No real artifact may influence Product behavior until Product consumer conformance I2 passes; the first real crossing is I3.

---

## H26. Reverse-dossier ingestion is incomplete

WP-I.5 mentions Product feedback and failed-adoption triage (`LAB_PLAN.md:439-441`) but does not define validated reverse records for all intended classes:

- defect findings;
- backend qualification;
- statistical-protocol improvements;
- failed-adoption reports.

It also does not require the backlog promotion fields from chapter 18: owner, validation lane, acceptance criteria, and expected evidence artifact (`claude-spec/18-engineering-standards.md:43-45`).

### Correction

Define reverse-dossier schemas, preserve Product provenance, and formalize promotion into `HARD_REMAINDER_PLAN.md`.

---

# Medium-severity execution and maintainability findings

## M1. Many WPs are epics, not reviewable TDD work packages

Examples include:

- WP-2.1: a genome, eleven model families, compatibility matrix, and compiler (`LAB_PLAN.md:219-223`);
- WP-2.3: seeding, benchmark selection, three archives, reproduction, crossover, mutation, resume, and persistence (`LAB_PLAN.md:229-235`);
- WP-2.8: speciation, scheduler, novelty, MAP-Elites, elites, pooling, process evaluation, and checkpointing (`LAB_PLAN.md:251-256`);
- WP-3.3: the complete statistical analysis layer (`LAB_PLAN.md:283-287`);
- WP-4.5: nearly the entire Primordia engine (`LAB_PLAN.md:319-322`);
- WP-6.4: Tier C, Tier D, Tier E, and runtime-envelope scaling (`LAB_PLAN.md:378-382`).

The opening recognizes that WPs need expansion, but the current unit still becomes the progress checkbox and dependency node. A single checkbox can stay open for weeks and hide partial integration, or close despite omitted sub-capabilities.

### Recommendation

Split each epic into independently testable WPs in the consolidated plan. A good WP should have:

- one primary behavior;
- one or two stable interfaces;
- explicit prerequisites;
- a bounded test set;
- one evidence artifact;
- a clear rollback boundary.

---

## M2. Dependencies are shown only at phase granularity

The linear phase map is useful (`LAB_PLAN.md:54-62`), but several WPs have cross-phase or intra-phase dependencies that are not encoded. Examples:

- benchmark audits depend on contender adequacy labels;
- dashboard decision slices depend on stable case and evidence schemas;
- native transfer depends on evidence registry promotion and backend classification;
- I1 fixtures depend on export schemas before Phase 5 finishes;
- Observatory depends on structured JSON from all earlier reporting surfaces.

### Recommendation

Give every WP `Depends on`, `Produces`, and `Blocks` fields. Use a small machine-readable dependency table or policy test to prevent execution out of order.

---

## M3. Exit gates need exact commands and artifact paths

Some WPs have good command-level verification, but later gates often use prose such as "browsable," "evidence-backed," or "one auditable outcome." These can pass through human interpretation.

### Recommendation

Every phase exit should specify:

- commands to run;
- expected exit codes;
- schemas/validators involved;
- exact generated artifact paths;
- required host/backend classes;
- minimum evidence counts;
- explicit failure conditions.

---

## M4. Work items lack requirement-level traceability

The plan references chapters, which is useful, but a chapter can contain dozens of normative obligations. The plan does not map each WP to requirement clauses, acceptance tests, and produced evidence.

### Recommendation

Add a compact traceability table per WP:

```text
Requirements: claude-spec/04 §Export Contract; claude-spec/13 §Honesty Rules
Verification: tests/contracts/test_export_roundtrip.py; compare output-quality
Evidence: artifacts/conformance/export-contract.json
Hosts: Linux + Apple Silicon
```

This is especially important because exact field lists are intentionally not duplicated (`LAB_PLAN.md:24-28`). Without requirement traceability, a later sub-plan can copy only the obvious fields and miss less prominent rules.

---

## M5. The single-writer lock design needs stale-lock and PID-reuse semantics

WP-0.7 proposes a lock file plus PID (`LAB_PLAN.md:134-136`). A PID alone is not a robust ownership identity across crashes, PID reuse, containers, or networked filesystems.

### Recommendation

Use an OS-level advisory lock where supported, with a lock record containing process start identity and host fingerprint. Specify stale-lock recovery and test crash/restart behavior. Keep DuckDB's ownership constraints explicit.

---

## M6. Atomic checkpoint publication needs directory durability

WP-0.6 correctly stages, fsyncs, checksums, and renames (`LAB_PLAN.md:128-133`), but durable publication on POSIX generally also requires fsync of the containing directory after rename. Manifest publication must itself be atomic and ordered after the payload is durable.

### Recommendation

Specify the full crash-consistency protocol and test crashes at every transition, including after payload rename and before/after manifest replacement.

---

## M7. Canonical digest serialization needs an explicit format

WP-0.5 says "canonical serialization" and a digest-field-omitted rule (`LAB_PLAN.md:120-127`) without defining float handling, map ordering, Unicode normalization, paths, timestamps, or schema version binding.

### Recommendation

Choose and document a canonical encoding, include schema/version identity in the hash domain, and provide cross-process golden vectors.

---

## M8. The plan freezes substantial implementation detail before the mandatory spike loop

The plan selects Python 3.13, specific libraries, package layouts, persistence details, and engine mechanisms at master-plan level (`LAB_PLAN.md:15-28`, `LAB_PLAN.md:72-97`). Much of that is grounded in the spec, but some choices still need viability validation in the target repository and CI environments.

### Recommendation

Mark each non-normative implementation choice as `accepted`, `provisional`, or `spike-gated`. Add explicit replacement criteria where library availability, Apple/Linux wheel support, or runtime behavior could invalidate the choice.

---

## M9. The plan does not define release/versioning milestones for the Lab itself

Interop schemas are versioned, but package/API releases, migration policy, artifact compatibility support windows, and the first conformance statement are not planned.

### Recommendation

Add a release-governance WP before I1 or Phase 7 that produces:

- package versions;
- changelogs;
- compatibility policy;
- conformance statement naming implemented spec versions;
- reproducible installation instructions;
- signed/tagged release artifacts if applicable.

---

# Low-severity clarity findings

## L1. Gate I0 is referenced but not defined inside the plan

The phase map and interop objective mention I0/I1 (`LAB_PLAN.md:61`, `LAB_PLAN.md:423-426`), but only the charter defines I0. The execution plan should not require readers to infer the precise exit from another document.

### Recommendation

Restate I0's executable acceptance criteria or link an exact charter section and pinned revision.

---

## L2. "Five-system" is ambiguous

The plan uses "five-system" for four engines plus Contenders (`LAB_PLAN.md:333-335`). This is understandable but should be defined once because Compare also presents projects-only and full-system views.

---

## L3. `MLX truth path` should consistently mean scientific-native rather than universally authoritative

The wording at `LAB_PLAN.md:17-22` is broadly correct, but the portability spec distinguishes native scientific evidence from fallback portability evidence rather than describing fallback as less truthful. Use precise labels such as `mlx_native`, `numpy_fallback`, and `portability_only` throughout.

---

# What the plan does especially well

## 1. It restores the normative Phase 0–7 structure

The phase map follows the roadmap rather than compressing load-bearing dependencies (`LAB_PLAN.md:54-62`; `claude-spec/17-roadmap-and-horizons.md:62-119`). This corrects the largest structural defect in the earlier program plan.

## 2. It separates scientific success from interoperability

The goal names `L-SCI` and `I1` independently (`LAB_PLAN.md:10-13`). Publishing readiness can no longer substitute for answering the Lab's scientific question.

## 3. It correctly declares specification precedence

The plan says `claude-spec/` is normative and wins on disagreement (`LAB_PLAN.md:15-18`). That is the right master-plan stance, provided the exact spec revision is pinned.

## 4. Architecture boundaries are strong

Independent engines, Compare as file-boundary orchestrator, and dependency-light Shared preserve the intended system architecture (`LAB_PLAN.md:15-18`, `LAB_PLAN.md:32-36`).

## 5. Most integrity fixes are front-loaded

Named RNG streams, atomic checkpoints, immutable evaluation records, read-only export, and measurement/proxy honesty directly incorporate the comparison's most important warning (`LAB_PLAN.md:120-155`; `spec-comparison.html:456-468`).

## 6. Contenders and Compare precede engine claims

The trust substrate exists before evolutionary engines (`LAB_PLAN.md:164-210`), matching the roadmap and preventing engine development from defining its own favorable comparison system.

## 7. Compare artifact design is substantially complete

Cases, budget-stamped packs, lane/accounting/repeatability states, trend JSONL, full-system/projects-only views, and ceiling-tie handling closely follow chapter 05 (`LAB_PLAN.md:183-200`).

## 8. Engine scientific identities are preserved

Prism, Topograph, Stratograph, and Primordia each retain distinct genomes, operators, compilers, evidence surfaces, and roles. Shared substrate is not allowed to absorb search-core identity.

## 9. Evidence memory is treated as infrastructure, not documentation

The append-only registry, checksums, supersession, copied compact artifacts, and registry-backed dashboard history are a strong rendering of chapter 12 (`LAB_PLAN.md:275-295`).

## 10. Transfer failure is designed to remain informative

The transfer phase includes all three regimes, explicit classification, provenance, accounting modes, and failure attribution (`LAB_PLAN.md:339-362`). The corrections above make the positive claim stricter but do not change the sound overall design.

## 11. Tier boundaries and portfolio roles are largely honest

The plan keeps Tier E admission-only, preserves Tier D as broad, requires evidence-backed roles, and permits the scientific program to conclude negatively (`LAB_PLAN.md:366-394`).

## 12. Phase 7 is no longer omitted

Performance discipline, Observatory, and scheduled trend detection are present (`LAB_PLAN.md:398-419`). This is a major completeness improvement.

## 13. Interop is treated as real implementation work

Mechanism dossiers have a schema and validator, fixtures include invalid/corrupt/old-version cases, and producer conformance is its own suite (`LAB_PLAN.md:423-441`). This is much stronger than treating chapter 19 as prose-only publishing guidance.

---

# Recommended restructuring of the plan

## 1. Keep the phase structure; revise the execution unit

Do not rewrite the roadmap. Instead, convert each current epic WP into smaller WPs while keeping the Phase 0–7 ordering.

Recommended WP template:

```markdown
### WP-X.Y — Outcome-oriented title

**Requirements:** exact spec sections/IDs  
**Depends on:** WP IDs  
**Produces:** stable interfaces and artifact paths  
**Hosts/backends:** required execution classes  
**Tests first:** named test files/cases  
**Implementation:** bounded behavior only  
**Verify:** exact commands and expected results  
**Evidence:** machine-readable artifact proving completion  
**Failure conditions:** conditions that keep the WP open
```

Keep the expanded checklist in `CONSOLIDATED_PLAN.md` or the PR description, not in a competing active plan file.

## 2. Add a pre-Phase-0 bootstrap gate

Create **Gate B0 — Reproducible authority and repository bootstrap**:

- repository exists on a non-main implementation branch;
- governing specs/charter are pinned;
- provenance manifest is checked in;
- package skeletons exist;
- both CI hosts execute a no-op workflow;
- single-plan policy test is green.

This resolves several Phase 0 ambiguities cleanly.

## 3. Add cumulative gate language

State explicitly:

> Later gates include all earlier standing gates. Benchmark admission, output quality, seed coverage, backend qualification, artifact validation, and contender adequacy are cumulative requirements; satisfying one never substitutes for another.

This is particularly important for Tier C and `trusted-extended`.

## 4. Introduce evidence classes in every phase exit

Each exit should say whether its output is:

- contract evidence;
- exploratory scientific evidence;
- portability evidence;
- decision-grade scientific evidence;
- producer-conformance evidence.

This prevents one-seed probes, fallback runs, and fixture tests from drifting into stronger claims.

## 5. Add an explicit interop gate table

Repeat the charter's I0–I3 meanings in executable form:

| Gate | Lab-plan meaning |
|---|---|
| I0 | Versioned schemas and fixture corpus exist |
| I1 | Fixtures plus real runtime artifacts pass producer conformance |
| I2 | External Product/reference consumer passes; not owned by Lab plan |
| I3 | First real import is registered end to end; not authorized by I1 alone |

---

# Prioritized revision checklist

## Must fix before creating the new repository

- [ ] Replace per-WP active plan files with single-plan-compatible expansion.
- [ ] Pin `claude-spec`, `PROGRAM_CHARTER.md`, and Product chapter 19 with provenance.
- [ ] Correct the budget contract: add `resumed_evaluations`; remove partial-run overrun exemption.
- [ ] Resolve the Phase 0 `contracts import everywhere` and resume-equivalence contradictions.
- [ ] Make both Linux and macOS CI real Phase 0 gates.
- [ ] Complete the export contract models/writers for manifest, results, and summary.
- [ ] Add physical test-label and active-speciation integrity obligations.

## Must fix before Phase 1/2 execution

- [ ] Add required image and language-modeling contender floors.
- [ ] Add floor adequacy labels and weak-floor blocking.
- [ ] Complete lane non-decision states and engine-only claim restrictions.
- [ ] Complete dashboard decision surfaces and backend/hardware filters.
- [ ] Upgrade Linux fallback from export smoke to compare-grade tiny execution.
- [ ] Move MAP-Elites/QD extras out of Phase 2.
- [ ] Add missing Topograph hardware-aware scope or narrow the phase claim.
- [ ] Add engine-specific telemetry conformance tests.

## Must fix before Phase 3/4 execution

- [ ] Preserve distinct statistical, grouped-report, and PR decision enums.
- [ ] Enforce `evidence validate --require-artifacts` in CI.
- [ ] Add non-parametric tests and mandatory diagnostics.
- [ ] Require runtime tradeoff telemetry in advancement evidence.
- [ ] Make Tier B audits zero-blocker and explicit.
- [ ] Add full CLI/export conformance for Stratograph and Primordia.
- [ ] Define Primordia artifact semantics and reconstruction tests.

## Must fix before Phase 5/6 scientific claims

- [ ] Pin native transfer to MLX and classify fallback separately.
- [ ] Require `charged_prior` confirmation for positive budget-matched transfer claims.
- [ ] Use the exact transfer validation sequence, including Tier C @128 exploratory.
- [ ] Encode matched-regime validation and positive-gain threshold.
- [ ] Pre-register QD descriptors, controls, diversity thresholds, and quality margin.
- [ ] Combine Tier C benchmark hardening with chapter-12 seed gates.
- [ ] Quarantine one-seed envelope probes as exploratory.
- [ ] Define decision-complete positive and negative L-SCI matrices.
- [ ] Constrain portfolio decisions to engine-only evidence.

## Must fix before Phase 7/I1 closure

- [ ] Expand the performance measurement matrix.
- [ ] Replace "Observatory browsable" with full acceptance tests.
- [ ] Replace the two-week-only automation gate with cadence and minimum evidence counts.
- [ ] Add compatibility/supersession semantics to interop versioning.
- [ ] Define a complete mechanism-dossier/provenance envelope.
- [ ] Require fixture manifests with expected accept/reject/stale/loss behavior.
- [ ] Require real runtime-produced artifacts for every export surface at I1.
- [ ] Encode the I1/I2/I3 authorization boundary.
- [ ] Define all reverse-dossier classes and backlog-promotion rules.
- [ ] Publish a Lab conformance statement and release/compatibility policy.

---

# Final verdict

`LAB_PLAN.md` has the right high-level design and should remain the basis of the Lab execution plan. It is substantially aligned with the current `claude-spec`, incorporates the most valuable cross-spec integrity lessons, and is far more complete than the earlier program-level staging.

The remaining issues are mostly not reasons to redesign the Lab. They are reasons to make the plan's contracts and gates as strict as the science it intends to support. The highest-value revision is to turn every broad prose exit into a cumulative, machine-verifiable acceptance bundle while preserving the clean Phase 0–7 dependency chain.

**Recommended status:** `REVISE_BEFORE_BOOTSTRAP`.
