---
document_kind: execution_plan
status: active
revision: 2
version: "2"
authoritative: true
b0_repository_model:
  python_package_skeleton_count: 7
  data_only_skeleton: shared-benchmarks/
  benchmark_helpers_module: evonn_shared.benchmarks
  data_only_check_script: scripts/ci/benchmarks-checks.sh
  python_import_validation: required
  data_skeleton_validation: layout_and_loader
---

# EvoNN Lab — Consolidated Execution Plan

**Updated:** 2026-09-09. Revision 2 remains the governing plan baseline; this
consolidation updates execution status without changing specifications or gates.

This is the sole execution plan. Expand work packages here or in a PR-local
checklist. [README.md](README.md) owns capabilities and operating instructions;
[PROJECT_HISTORY.md](PROJECT_HISTORY.md) owns completed work, decisions and
verification references. Pinned [Lab specifications](claude-spec/README.md)
win on disagreement. The [program charter](PROGRAM_CHARTER.md) separates Lab,
Product and interop; Product implementation is outside this repository's plan.

## Immediate Next Actions

Documentation consolidation (#23/#26), CodeRabbit selection (#24), the catalog
freeze and fixture integration (#25), and its canonical authorization (#27)
are merged. Phase 0 contract acceptance is bound in
`governance/phase0-acceptance.json`: exact canonical commit/tree, successful
Linux/macOS evidence, immutable freeze digests and every parent WP's tests.

**Phase 1 Contenders + Compare is implemented in #29/#30.** Their required
hosted checks govern integration of the reviewed implementation. The runtime
receipt `governance/phase1-runtime-evidence.json` records 336 successful fits,
three core@64 seeds plus core@128 and smoke@16; core audit passes with zero
blockers and every run is L3.

**Phase 2 Prism + Topograph is implemented in #31.** The compact
`governance/phase2-runtime-evidence.json` binds 13 real runs / 896 fits, three
core@64 seeds, Tier-A@64 and the Contenders core@128 floor. All 13 exports
reach L3; the recorded verification consumer replays 64 neural winners and core admission
passes as `trusted-core`. Independent reviews and real process-death tests
cover both engines; both required hosted lanes gate merge of the final revision.

Phase 3 registry/statistics is merged in #32 (both hosted lanes green). Its runtime receipt
`governance/phase3-runtime-evidence.json` binds a real three-seed before/after
comparison: L4, no material change, no advancement claim. Full dependencies
are versioned release assets, rehydrated and revalidated on both CI hosts.
Phase 4 implementation and short qualification are complete: independent
Stratograph/Primordia runtimes, matched ablation and motif commands, strict banks,
real-text Tier B and four-engine LM integration. The compact receipt
`governance/phase4-runtime-evidence.json` binds 13 L3 runs / 304 fits and 80
replayed winners. The five-system Tier-B@16 contract audit has zero blockers.

**Completed comparison:** the user-authorized optimized campaign finished on
2026-09-09 at 00:30 CEST: 30/30 runs, 2,880/2,880 fits, zero failures; Tier B
budgets 64/128 × seeds 42/43/44 × five systems. The
[analysis receipt](governance/tier-b-comparison-20260909.json) and
[interpretation](PROJECT_HISTORY.md#tier-b-comparison--2026-09-09) bind the exact
producer and per-seed measurements. Decision-grade benchmark admission now
passes with zero blockers. Three seeds meet the local coverage minimum, but
the initial post-run analysis did not close the scientific exit; the explicit
L4 follow-up below remains distinct from automatic scientific promotion.
The original timed-out campaign remains untouched; existing limits remain.

**Completed follow-up (2026-09-09):** large-state reporting now preserves valid
protocol identities and uses the bounded native state reader. Historical registry
rows still validate with their original observation policy; a separate
`evidence cohort-report` projection revalidates exports and evaluates explicit
engine/floor/budget contrasts. All **24 declared contrasts reach L4 evidence
quality** with three seeds and zero blockers. L4 does not authorize advancement,
protected-test performance or a broad superiority claim. Source-bound campaign
manifests reconcile the two historical host-hash encodings; budget contrasts
permit only the mathematically derived training-total cap to scale.

Stratograph's matched five-variant × three-seed @64 ablation completed **960
fits in 13m15s**. Shared controls reproduce all twelve prior scores exactly.
Flat image accuracy averages **57.96% versus 25.09% shared**. Unsharing alone
reaches 24.26%; removing cloning stays at 25.09%. A separate six-fit fixed-genome
probe improves image accuracy from **23.98% to 44.63%** by normalizing hierarchy
features with training-only statistics. This identifies an actionable proxy
limitation; no new default or end-to-end hierarchy claim has been introduced.

The [confirmation protocol](governance/tier-b-confirmation.json) is frozen before
execution: **eight fresh seeds 45–52**, 48 runs / 4,608 fits. Discovery seeds
42–44 are excluded. Eight nonzero same-sign pairs can clear the five-contrast
Holm family; six cannot, even at their minimum exact two-sided p-value. The
protocol fixes named neural/boosted baselines, quality margins, the joint
Primordia quality/runtime criterion and balanced engine order. Stronger model
classes are additional pressure, not assumed empirically stronger scores.

The isolated execution checkout is
`/Users/timokruth/Projekte/EvoNN-confirmation-v2-20260909`, pinned to
`7da8e76` with locked optional dependencies. Its **16 manifests passed preflight**.
Execution started on **2026-09-10 at 11:33 CEST**, using fresh manifests in
`.artifacts/confirmation-execution-20260910` after a network hostname change;
source, libraries, specifications and dataset provenance are unchanged. The
original unused manifests remain retained. A 64-fit enhanced-floor qualification
completed in 203 seconds with no failed fits; XGBoost, LightGBM, CatBoost, CNN
and Transformer all ran. The initial qualification exposed a private sklearn
validation assumption in external estimators; the fix preserves sklearn and
explicit third-party validation, and the failed producer remains retained.

**Confirmation evaluated (2026-09-10):** all **48 runs / 4,608 fits** finished
without failures or repairs in 108m09s; all exports validated and **128 native
winner replays passed**. The unchanged frozen five-contrast family reaches L4.
The [result receipt](governance/tier-b-confirmation-results-20260910.json) binds
all per-seed measurements, criteria and source artifacts. Prism LM passes both
predeclared comparisons (Holm p=0.0391); Topograph regression fails confirmation
(Holm p=0.2344 against CatBoost and 1.0 against the required floor). Primordia's
joint tabular-quality/full-pack-runtime criterion passes narrowly: quality CI
[-2.831%, +4.595%] against a -3% tolerance, runtime ratio CI [0.6839, 0.7406]
against an upper-bound requirement of 0.75. Image/LM parity is not claimed.
Guardian state is `complete`; no new campaign is scheduled by this result.

**Next, in priority order:**

**Completed and evaluated (2026-09-11):** the
[all-engine high-budget result](governance/all-engines-high-budget-results-20260911.json)
binds all 80 original runs / 15,360 successful fits, 128/256 budgets and seeds
53–60, producer `e1d005a`. All sixteen cases were combined before baseline
admission; 80 records validated and 256 trained winners replayed. All four
predeclared contrasts are L4 with eight seeds and Holm p=0.03125. Prism,
Topograph and Primordia clear the aggregate material-gain criterion against the
required floor; Stratograph is materially negative. The full expanded pool is
reported separately, and task-level/engine-to-engine rankings remain descriptive.
Prism leads native mean quality, Primordia remains faster with lower image/LM
quality, and Topograph's additional runtime is not justified by a native quality
lead in this cohort. More budget does not resolve Stratograph's shared-proxy
deficit (digits 29.76% → 33.99%). The protected text test is still unused.
No additional training is scheduled by this evaluation.

**Standing user requirement (2026-09-10):** every new comparison includes Prism,
Topograph, Stratograph and Primordia on every declared benchmark/budget/seed
combination, plus Contenders baselines. Focused research questions can restrict
the predeclared statistical tests, not the engine roster. Report all four;
failed or missing executions leave the comparison incomplete. Do not omit
Stratograph while its proxy is being improved. The completed focused confirmation
remains historical evidence and does not satisfy this new four-engine requirement.

1. Qualify the opt-in Stratograph v2 implementation described in
   [its runtime README](EvoNN-Stratograph/README.md#explicit-version-2-research-execution).
   Implemented: training-only hierarchy normalization with saved replay buffers;
   local projection identities and explicit randomization; representation-aware
   inheritance without epoch discounts; bidirectional macro edits and wider
   mutation support; protected exploration, behavioral novelty and archive
   revisitation; charged screening/full-fit diagnostics; differentiable shared
   cells and an extensible primitive registry. Legacy execution remains the
   default when no research policy is declared. This is implementation progress,
   not scientific qualification or an engine promotion.
   Freeze separate normalization, inheritance, search and evaluator ablations
   before their combined confirmation. Set `evolve_representation: false` for
   fixed-representation diagnostics. Every new comparison includes all four
   engines and Contenders on every declared combination, with fresh confirmation
   seeds and matched work accounting. Preserve historical producers/results;
   leave failed or missing runs visible and the comparison incomplete. Evaluate
   quality together with coverage, revival of weak candidates and screening rank
   reversals; never remove a supported direction solely on short-run performance.
2. Qualify Prism's implemented exploration policies, documented in
   [the central runtime instructions](README.md#prism-exploration-policies).
   `open` combines archive parents, protected weak lineages and fresh starts;
   transfer-coverage and learning-progress epoch allocation; broader reversible
   mutations and composable blocks. `legacy`, `archive`, `training` and `broad`
   remain explicit controls. Per-epoch and lineage telemetry, cold-initialization
   controls, weight-bound optional Adam continuation, and an optional MLX optimizer
   are implemented. Existing genome identities and frozen evidence remain intact.
   Package/contract tests and native crash/resume/replay checks establish runtime
   correctness, not scientific improvement. Keep the NumPy optimizer default:
   the initial tiny MLX-CPU microbenchmark favored it over native optimizer arrays.
   Freeze separate archive/training/proposal ablations with fresh seeds, complete
   all-engine/Contenders matrices, per-task quality margins, diversity/revival
   criteria and both work and wall-time accounting. A cold-search control does
   not ensure identical later proposals; use the implemented `finalist-config`
   and `fixed_genomes` mode to freeze architectures and per-fit training
   allowances. Prior discovery remains explicitly `reported_prior`, not a
   charged-prior gain claim. Retain negative/inconclusive
   variants as research options instead of excluding their architectural paths.
   Use the confirmed bounded Prism LM finding to design a separate, frozen
   generalization comparison. The additive `language_breadth_v1` workload includes
   longer contexts, Aesop and delayed memory alongside the original LM task;
   runtime safety and contender adequacy remain unqualified. Follow-on workload
   development includes context-removal diagnostics, distribution shifts and
   harder image/tabular tasks; phase profiles should guide any worker-reuse or
   transport optimization. These are not delivered or speedup claims. Include all four
   engines and Contenders before
   accessing the protected text test split. Keep
   validation selection separate from final testing. Retain Primordia as a
   candidate for efficient tabular search, with its narrow tolerance margin and
   weaker image/LM outcomes explicit. Do not present Topograph as a confirmed
   regression leader or extend the fixed eight-seed test after seeing results.
3. Integrate the analysis-tested exact-content catalog parse cache into the maintained validation path, then remeasure
   with identical verdicts. Profiling the source-revalidated report found
   **29,076 catalog lookups**, accounting for roughly 96% of profiled cumulative
   time. Avoid a global cache that could hide changed catalog bytes. No timing
   from cProfile is a claimed unprofiled speedup. The September 11 analysis used a bounded
   parse-only wrapper, checked against all 17 catalog/pool YAML files and malformed
   input cases. It still reads and hash-checks source bytes; core integration is open.

**Superseded PR #37 implementation comparison (2026-09-11):** the user requested
the source-bound before/after comparison needed for merge readiness. The frozen
[protocol](governance/pr37-comparison-protocol-20260911.json) declares all four
engines plus Contenders at Tier-B budgets 64/128 on fresh seeds 83/89/97, in
both revisions: 60 runs / 5,760 fits, MLX CPU and 12 configured epochs. Execution
stopped incomplete after four runs / 256 successful fits, at the user's
request to merge PR #36 first. PR #36 merged at `61543ef`; it includes the
Primordia runtime implementation and its source-bound contract qualification.
The remaining PR #37 changes cover CI, regression tests and this record, with
no runtime difference from that main. The old comparison will not resume. The separate
[status receipt](governance/pr37-comparison-status-20260911.json) records all five
systems, including the unexecuted engines; eight saved Prism winners replay.
Do not relabel the frozen revision pair after main changes. Historical evidence
remains unchanged; known policy/host-identity differences remain blockers.
The incomplete comparison supplies no merge qualification and does not close
the scientific ablation/confirmation work below.

4. Qualify Primordia's implemented `breadth_v2` policy, documented in
   [its runtime README](EvoNN-Primordia/README.md). Independent founders,
   learning-progress early stopping with patient slots, quality/diversity/young/
   reservoir/Pareto retention, optional cheapening, fresh retraining, configurable
   size envelopes, branching, mutable sparsity, causal lag processing and
   composed-motif mutations are implementation changes, not established gains.
   Preserve `legacy_v1` as the frozen scientific reference. Predeclare separate
   training, retention/mutation and representation ablations before combined
   confirmation, using fresh seeds and all four engines plus Contenders on every
   declared combination. Measure both matched-proposal and matched-compute
   outcomes, behavioral coverage, lineage revival and fresh/inherited agreement.
   Do not eliminate a supported operator or representation for poor early scores.
   No new scientific campaign or protected-test access follows automatically.

5. Qualify the implemented opt-in [Topograph research modes](README.md#topograph-research-modes).
   `mechanics` is the common v2 control; test `training`, `archive` and `broad`
   additions separately before combined `open` confirmation. Preserve the original
   legacy evidence. Use fresh seeds and freeze quality/non-inferiority margins,
   descriptor/coverage criteria and the statistical family before execution.
   Include all four engines and Contenders on every declared combination, with
   explicit Topograph policy in the campaign specification. Record effective
   structural changes, resource rejections, lineage revival, late learning,
   fresh/inherited agreement and matched-fit/matched-compute outcomes. Profile
   runtime stages before changing process isolation or penalizing costly families.
   Learned descriptors, broader dataset qualification and native cross-run seed
   ingestion remain separately scoped work; this implementation does not close
   WP-5.2, WP-6.2 or a scientific superiority gate.

The repeated low/mid admission and explicit L4 aggregate surfaces are now
available. WP-4.7's remaining preset/trusted-extended integration and the formal
Phase 4 exit still need their explicit acceptance; no automatic scientific,
portfolio or transfer promotion was made. Native cross-engine ingestion remains
Phase 5.

Supporting work: CodeRabbit automatic review is currently skipped by its
repository star-count policy; a green skipped status is not review evidence.
Two independent review agents cover the authorized review scope; measured policy validation
is dominated by Git subprocesses. Optimize only with equivalent verdicts and
comparable measurements. The evidence-retention proposal below is still a
proposal; obsolete copies may be removed after its tested policy migration.

### Implemented prerequisite — bounded campaign control and durable journal

**Requirements:** campaign planning/preflight, whole-campaign resume, scalable
attempt persistence requested before the larger comparison. This infrastructure
precedes the scientific Phase 4 exit; it does not claim that exit or Phase 5.
**Produces:** immutable campaign manifests, read-only preflight, locked stable
case/system slots with verified recovery, and versioned per-attempt journals
with periodic compact checkpoints. Existing exports and accounting stay intact.
**Tests:** reject manifest/source/data/backend drift and malformed matrices;
adopt completed runs after supervisor failure without fitting again; reject
live concurrent workers and unsupported incomplete Contenders recovery; resume
all four engines across transaction/row/checkpoint failures; reject broken
journal chains and measure storage growth without training.
**Verification:** 831 foundation tests and 86 Compare tests pass. A real
five-system Tier-B@16 campaign completed 80 fits with pause/resume counts 2/3/0;
the final resume changed no completed-run or event bytes. All exports are L3
and 16 neural winners replay. Two independent reviewers found no remaining
blockers. The compact campaign receipt binds producer and release evidence;
existing real resume/replay cases and both required CI lanes gate integration.
The prerequisite qualification started no large training campaign. Existing
256-proposal/1800-second limits remain; persistence scalability alone does not
qualify a larger runtime.
**Failure conditions:** duplicate fits/charges, changed comparison settings,
unbound cache or code, non-atomic state, weakened validation or a scientific
claim from implementation-only evidence.

## Execution Rules And Evidence

- **Architecture:** Python >=3.13, one uv workspace/lock, seven independent
  packages and a data-only benchmark directory. Engines never import one
  another; Compare invokes CLIs and consumes files. Shared contains contracts
  and infrastructure, not genomes, search or an engine runtime.
- **Backend classes:** `mlx_native` supports scientific engine-training
  evidence only after qualification; `numpy_fallback` is `portability_only`;
  `sklearn_contender` identifies the external floor. Do not silently mix cohorts.
- **Evidence classes:** `contract`, `exploratory-scientific`, `portability`,
  `decision-grade-scientific`, `producer-conformance`. The current synthetic
  report is `synthetic_contract_preparation`; it does not qualify an engine.
- **Cumulative gates:** benchmark admission, output quality, seed coverage,
  backend qualification, artifact validity and contender adequacy all apply.
  Every engine must hold L3 on Tier A and `tier1_core@64` before trusted claims.
- **Accounting:** preserve all nine accounting fields and seven declaration
  fields from claude-spec/03. No negative/over-budget/double-counted work;
  `partial_run` reflects incomplete coverage. Failure/invalid semantics and
  fresh versus inherited work stay explicit.
- **Persistence:** one OS-locked writer per per-run DuckDB; validated canonical
  RunWorkspace; deterministic named RNG streams; atomic/checksummed checkpoints;
  immutable evaluations and read-only export. See README for filesystem limits.
- **Claims:** five-system cohort means four engines plus Contenders.
  Engine-only cohorts support portfolio/parity decisions; contender-including
  cohorts support external-floor claims. Mixed evidence remains inconclusive.
- **Interop:** Lab I1 proves publishing readiness; real Product influence
  requires Product-owned I2 as well. Register the first crossing as I3.
- **Change discipline:** PRs with relevant tests and concrete review findings;
  no direct pushes to main. GitHub requires zero approving accounts and no
  last-push approval. Required Linux/macOS checks, up-to-date branches and
  resolved conversations still apply. Freeze amendments retain their separate
  producer/consumer evidence review; two GitHub identities are not a substitute.
- **Feature flags:** default off or to a demonstrated better default; preserve
  a way to restore prior behavior. Keep research scope separate from Product.

### Work-package expansion template

Before implementation, expand the active WP here or in its PR checklist:

```markdown
### WP-X.Y — Outcome-oriented title
**Requirements:** exact pinned spec sections
**Depends on / Produces / Blocks:** WP IDs, interfaces and artifact paths
**Hosts/backends:** required execution classes
**Tests first:** named behavioral and rejection cases
**Verify:** exact commands and expected outcomes
**Evidence:** machine-readable artifact and evidence class
**Failure conditions:** what keeps the WP open
```

Split every `[epic]` into these sub-WPs. Preserve numbering and dependencies;
record a dependency reason before changing order. Completed execution notes go
to project history, not a second active plan. Technology choices mandated by
the spec are accepted; implementation defaults remain provisional until tested.
Bootstrap MLX wheel availability has been demonstrated; engine qualification
still requires the later real runtime evidence.

### Parallel execution and integration

Lab and Product can develop independently; fixtures and co-signed schemas allow
parallel build while real artifact influence waits for Lab I1 and Product I2.
Within a Lab phase, the ownership blocks below are the single lane map:
**freeze interfaces → parallel lanes → cross-review → joint integration → joint gate**.
Use `agent/p<N>-lane-<a|b>-<slug>` and `agent/p<N>-integrate` when executing lanes.
Do not overlap file ownership; shared packages require explicitly disjoint
modules. A frozen interface change requires a recorded amendment review.
Review the other lane against exact specs, WP requirements and integrity tests.
Integration runs full CI on both hosts, cross-cutting suites and exit commands.
With one worker, execute lanes sequentially through the normal PR flow and keep
integration acceptance. B0, Foundation Integrity Gate, phase exits, transfer
proof, L-SCI, portfolio status and release governance remain joint decisions.


| Phase | Lane A | Lane B | Joint work |
| --- | --- | --- | --- |
| 0 | WP-0.2, 0.3, 0.4, 0.5 | WP-0.1, 0.6, 0.7, 0.8, 0.9 | WP-0.10 integrity gate + phase exit |
| 1 | WP-1.1, 1.2, 1.7, 1.8 | WP-1.3, 1.4, 1.5, 1.6 | phase-exit fair-matrix run |
| 2 | WP-2.1–2.4 | WP-2.5–2.9 | WP-2.10 + exit cohort |
| 3 | WP-3.1, 3.4 | WP-3.2, 3.3 | WP-3.5 + phase exit |
| 4 | WP-4.1–4.4 | WP-4.5, 4.6, 4.7 | WP-4.8 + exit cohort |
| 5 | WP-5.1, 5.2 | WP-5.3 | WP-5.4 transfer proof campaign |
| 6 | WP-6.1, 6.2 | WP-6.3, 6.4 | WP-6.5 portfolio statuses + WP-6.6 L-SCI |
| 7 | WP-7.1, 7.2 | WP-7.3, 7.4 | WP-7.5 release governance + phase exit |

## Gate B0 — Closed Bootstrap

- [x] **B0.1** Canonical Lab repository and branch/PR workflow exist.
- [x] **B0.2** Normative sources are remote-pinned with reproducible provenance.
- [x] **B0.3** Seven importable packages and one tested data-only skeleton exist.
- [x] **B0.4** Import-direction policy is enforced.
- [x] **B0.5** Hosted Linux/NumPy and macOS/MLX bootstrap probes are preserved.
- [x] **B0.6** Single execution plan and transition-safe governance are enforced.

Gate B0 is closed by its anchored schema-2 report and status record. Historical
hosted evidence tests `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224`: Linux
`29658842317`, macOS `29658842318`. It is `bootstrap_probe_only`, not scientific
evidence. The catalog freeze PR and separate authorization attestation are
merged; freeze v3 is `merged_verified`. History retains the exact B0 bindings,
review records and probe paths. This state does not imply Phase 0 acceptance.

## Phase 0 — Workspace, Contracts, Integrity Foundation

**Objective:** validated contracts, benchmark resolution and a permanent
integrity gate proven against executable skeletons. Spec: claude-spec/01–04,
/13, /18. All ten parent checkboxes below represent acceptance, not whether
implementation exists. The reviewed acceptance receipt closes these ten
parents with contract evidence. It preserves the distinction between ordinary
export fixtures, the actual no-op persistence proof, and future engine evidence.

### Accepted requirement-to-test evidence

[`governance/phase0-acceptance.json`](governance/phase0-acceptance.json) is the
single machine-readable matrix for WP-0.1–0.10. It binds the actual canonical
attestation merge to both successful hosted workflows. Their tested PR merge
has exactly the same tree and ordered parents as that canonical merge; the
checkout logs and freshly downloaded runtime/integrity artifacts establish the
mapping. These equivalent contract checkouts are identified separately, not
reported as tests of an identical commit SHA or independent scientific repeats.

The hosted checks cover all 776 Shared foundation tests, the governance and
import/dependency policies, catalog inventory, and platform package checks.
Eight benchmarks and all three packs pass metadata and export composition.
The reference reports demonstrate real kill/resume and label/budget integrity.
No dataset execution, demonstrated contender adequacy or qualified engine
backend is inferred from this acceptance.

The historical dataset loader has a two-way train/validation split. A protected
third split is required only by a protocol that declares it; it is not a general
Lab Phase 0/1 gate. Introducing one changes split semantics and requires new
IDs and provenance. Regular export fixtures and the no-op integrity consumer
provide separate contract evidence; no new SystemId or synthetic engine export
is needed. Never relabel no-op agreement scores as real benchmark results.

### WP-0.1a — Cross-host coverage and economical CI

**Requirements:** claude-spec/13 portability; /18 Testing Expectations.
**Depends on / Produces / Blocks:** WP-0.1 and WP-0.7a; consistent hosted
coverage and bounded CI improvements; contributes to Phase 0 acceptance.
**Hosts/backends:** Linux/NumPy and macOS/MLX with unchanged required job names.
**Tests first:** workflow contracts for triggers, coverage, cancellation,
read-only permissions, evidence generation/validation and explicit upload paths.
**Verify:** `scripts/ci/foundation-checks.sh`; `scripts/ci/b0-policy-checks.sh`;
both hosted lanes. The latter requires full Git history.
**Evidence:** #11/#13/#14/#20 and the final-main runs linked in project history.
**Failure conditions:** lost coverage, skipped required checks, changed historical
policy verdicts or a speed claim without comparable measurements.

Implemented: scoped immutable-Git-read caching; no duplicate feature push runs;
a single foundation selection on both hosts; independently callable package
scripts; required hosted synthetic report generation/validation/upload.
Profiling found 246 Git subprocesses in one 4.36s local freeze validation;
4.18s was spent inside Git calls. No optimization is claimed from this single
measurement. Any bounded change must retain the same historical cases. Final main's macOS B0 step took 18m46s; foundation took 35s. These
are observations from one run, not a stable benchmark. PR #24 corrected CodeRabbit
selection; its in-content review and the 28 files processed on #25 verify the
fix. Test docstrings should explain non-obvious contracts or invariants; no
blanket docstring expansion is needed merely for a bot percentage.

### WP-0.7a — Transactional evidence and safe run-directory I/O

**Requirements:** claude-spec/01 storage; /04 records/run directory;
/18 Operational Safety Rules.
**Depends on / Produces / Blocks:** WP-0.7; hardened store/workspace and reader;
prerequisite for reference integrity acceptance.
**Hosts/backends:** Linux and macOS; DuckDB, independent of engine runtime.
**Tests first:** transaction rollback/recovery; corrupt-chain rejection;
symlink/hardlink refusal; shared reader/exclusive writer ownership; atomic
publication and unchanged evidence on read/export failures.
**Verify:** `scripts/ci/shared-checks.sh`; `scripts/ci/phase0-contract-checks.sh`;
`scripts/ci/b0-policy-checks.sh`; both hosted lanes.
**Evidence:** merged #10, #15, #16 and #19; exact integrations in history.
**Failure conditions:** partial logical records, source mutation during export,
unsafe-path mutation, or unsupported filesystem guarantees being claimed.

The bounded implementation and cross-host review series is complete. Parent
WP-0.7 acceptance is bound in the phase evidence receipt. `_run_io` already
centralizes no-follow descriptor I/O and atomic no-clobber publication.

### WP-0.1b — Bounded versioned-contract and catalog amendment

**Requirements:** claude-spec/01 boundaries; /02 immutable canonical identity;
/04 compatibility; /18 review/documentation; the recorded upgrade process.
**Depends on / Produces / Blocks:** current freeze v2 and WP-0.7a; reviewed
replacement freeze/validator and catalog-addition rules; precedes WP-0.8.
**Hosts/backends:** both hosted lanes; no engine runtime dependency.
**Tests first:** reject changed signatures, field meanings, canonical bytes,
rewritten IDs and altered historical evidence; accept explicitly compatible
catalog additions; compare old/new validators on historical fixtures.
**Verify:** full policy/contract suites on both hosts, independently recomputed
historical digests, and the specified canonical merge/attestation sequence.
**Evidence:** exact old/new surface inventory, source diff, provenance and
traceability impact, supersession rationale, candidate commit/tree/digests,
producer/consumer review records and hosted results.
**Failure conditions:** historical evidence becomes unverifiable, hashes stand
in for review, validator/trust-anchor updates diverge, or any review is missing.

The proposal separates versioned public contracts, immutable catalog semantics,
and behavior-preserving internal/test edits. Existing IDs never change meaning;
new IDs require provenance, split/metric definitions, pack membership and
contender expectations. The reviewed validator and trust-anchor update must be
atomic. Follow [SPEC_UPGRADE_PROCESS](governance/SPEC_UPGRADE_PROCESS.md).
Freeze v3 is effective after #25 and #27. Closed PR #9 admitted nothing;
its successor carried the complete reviewed amendment. Extraction of
remaining private export/catalog parser helpers stays conditional on amendment
and demonstrated value; keep seven package boundaries and avoid a framework.

### Proposed evidence-retention simplification within WP-0.1b

Historical filenames and prose are not product requirements. Replace the
historical checkout-copy obligation with verification at the already pinned
Git commit, while keeping current contracts locally readable.

- **Remove after migration:** superseded B0 and v1 review prose, the 754-line
  Task 6 report, and the separate dynamic-import experiment log. Preserve their
  decisions in PROJECT_HISTORY and verify original evidence through exact Git
  commits/blobs. Keep active v2 reviews only until their replacement is accepted.
- **Validator change:** distinguish active normative inputs from historical
  evidence. Continue checking the latter's exact commit ancestry, object type,
  mode and SHA-256, with replacement objects disabled. Missing, substituted,
  rewritten or shallow-history evidence must still fail. Removal of the old
  working-tree copy alone should pass; do not fall back to an unverified copy.
- **Test change:** replace historical prose/filename assertions with corruption,
  forged-review identity/digest, missing-object and history-transition cases.
  Retain all import-boundary, RNG, accounting, atomicity, resume and export
  behavior checks. Verify the same historical accept/reject cases against both
  validator versions, except the explicitly retired checkout-copy obligation.
- **Keep:** active Lab requirements, the Lab/Product consumer boundary, current
  schema contracts and behavioral/golden fixtures. These determine what the
  software must do and which claims its evidence supports.
- **Acceptance:** an exact removal inventory and source-reference map, atomic
  validator/trust-anchor update, passing regression cases and both hosted lanes.
  No new archive directory full of duplicate prose; no acceptance inferred from
  deleting a test or reducing its assertions.

This is a proposed storage-policy change, not an active waiver of the freeze.
It does not require changing the scientific contracts or weakening reviews.

### WP-0.10a — Reference integrity integration and acceptance

**Requirements:** claude-spec/03 accounting; /04 exports/integrity;
/18 resumable lifecycle; WP-0.10 protected-label capability boundary.
**Depends on / Produces / Blocks:** WP-0.7a, WP-0.1a and accepted WP-0.8;
immutable reference acceptance fixtures; blocks Phase 0 exit and Phase 1.
**Hosts/backends:** both hosted lanes; contract evidence only.
**Tests first:** uninterrupted/resumed row and checkpoint equality; declared
budgets and failed/invalid accounting; read-only export; seed/label identity;
selection cannot access protected labels; measured/proxy provenance.
**Verify:** `scripts/ci/foundation-checks.sh`; catalog admission checks;
`scripts/ci/b0-policy-checks.sh`; both hosted lanes.
**Evidence:** both hosted eight-case synthetic reports, all three
catalog/budget/export fixtures and the immutable requirement-to-test receipt.
**Failure conditions:** synthetic fixtures are called production/scientific
proof, placeholder hooks count as passing, or any parent is unaccepted.

The synthetic runner and probe are implemented, reviewed, merged and hosted.
They charge each candidate under an explicit policy, distinguish fresh and
inherited work, and recover a durable row ahead of its checkpoint without
reevaluation. Four kill boundaries cover failed and invalid attempts. Resume
rejects changed seed/config/label identities; diagnostics validate the complete
persisted state. These diagnostics are not the regular three-file export.
All three catalog packs pass budget/export fixture composition. The reference
gate is accepted with the full parent matrix and hosted evidence. The normative
requirements do not require a regular export from the no-op runner or a new
system identity. It does not claim general
exactly-once behavior before row commit. Engine resume hooks activate as engines
land; speciation behavior activates with Topograph, not a placeholder.

### Parent scope and phase exit

**Lane split & sync:** A owns WP-0.2–0.5; B owns WP-0.1 and WP-0.6–0.9;
WP-0.10 and the Phase 0 exit remain joint. Frozen interfaces are canonical
encoding/digests, export models and catalog-loader signatures. Freeze v3 adds
the reviewed catalog inventory; its exact canonical merge is verified below.
Supplemental consumer/inventory tests remain subject to normal reviewed CI,
without automatically extending the byte-frozen surface. Phase 0 acceptance
is bound separately in the immutable receipt; its ten parent items are closed.

<!-- phase0-interface-freeze:begin -->
```yaml
freeze_id: phase0-interface-freeze-v3
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: 0ece535d8b68c8701a17e404baa25dd6b20be52e
approved_tree: 1a65a5b343d43674025458718697dea923fb2d6e
digests:
  canonical_digest_rng: 1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc
  export_models: f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72
  catalog_loaders: f123d29b3c29464aa947e271c0b26ed74278eb528322a5fb808b3679b4a86fe5
reviews:
  - reviews/2026-09-07-phase0-lane-a-producer-v3-review.md
  - reviews/2026-09-07-phase0-lane-b-consumer-v3-review.md
status: merged_verified
lane_authorization: true
canonical_merge_commit: 322834900aa99a267b78b789a733e96ac205dd04
verified_at: 2026-09-07T15:49:25Z
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```
<!-- phase0-interface-freeze:end -->

- [x] **WP-0.1 Workspace tooling.** Root workspace config, ruff/pytest
  config, `scripts/ci/*-checks.sh` per package wired into the B0 CI lanes.
- [x] **WP-0.2 Export contract — all three files.** Strict models +
  round-trip writers/readers for `manifest.json`, `results.json`,
  `summary.json` with the complete claude-spec/04 surface (results incl.
  `task_kind`, memory, per-benchmark evaluation counts; manifest runtime
  block; summary budget echo + fairness flags + artifact digests).
  Valid/invalid fixtures covering unsupported/skipped visibility and
  schema-version compatibility.
  *Interfaces:* `Manifest|Results|RunSummary.model_validate_json`,
  `write_export(dir, m, r, s) -> ExportDigests`.
- [x] **WP-0.3 Budget models.** `BudgetDeclaration` (7 contract fields) +
  `BudgetAccounting` (9 accounting fields incl. `resumed_evaluations`)
  with the corrected validators from Global Constraints.
- [x] **WP-0.4 Telemetry + seeding models.** Envelope floor; 9 seeding
  fields with explicit-`unknown` semantics; ladder enum none|direct|staged.
- [x] **WP-0.5 Identity + RNG streams.** Content digests over a **defined
  canonical encoding** (documented map ordering, float formatting, Unicode
  normalization, no absolute paths/timestamps in hash domain, schema
  version bound into the hash; cross-process golden vectors);
  digest-field-omitted rule. `derive_stream(root_seed, name)` for the
  named streams (search, data, split, init, order, augmentation, mutation,
  benchmark_sampling, worker, stats) — deterministic, scheduling-independent.
- [x] **WP-0.6 Atomic checkpoints.** Stage → fsync payload → checksum →
  atomic rename → **fsync containing directory** → atomic manifest update
  referencing previous checkpoint digest. Crash tests at every transition
  (after payload rename; before/after manifest replacement); previous
  checkpoint stays authoritative until manifest commit.
- [x] **WP-0.7 RunStore + RunWorkspace.** Per-run DuckDB schema (runs,
  append-only evaluations, artifacts, metadata). Single-writer ownership
  via OS advisory lock + lock record (process start identity + host
  fingerprint), stale-lock recovery semantics, crash/restart tests — PID
  alone is not ownership. `RunWorkspace` creates/validates the full
  canonical run directory; end-to-end fixture builds one, rebuilds
  `report.md`, and verifies artifact references without mutating evidence.
- [x] **WP-0.8 Benchmark catalog + packs.** YAML schema per claude-spec/02
  (explicit direction, ceiling semantics, required contenders, runtime
  class); loaders; the 8 `tier1_core` benchmarks + smoke variants; packs
  `tier1_core`, `tier1_core_smoke`, `tier_a_contract`; append-only
  canonical ID registry.
- [x] **WP-0.9 LM cache validation.** Existence/size/checksum for
  byte-level LM caches (used from Phase 4).
- [x] **WP-0.10 Foundation Integrity Gate.** Permanent CI suite:
  `test_rng_streams_deterministic_and_independent`;
  `test_resume_equals_uninterrupted` — proven in Phase 0 against a
  **deterministic no-op reference resumable runner** (a minimal engine
  skeleton exercising checkpoint/resume for real), with mandatory
  engine-specific instantiations added as each engine lands;
  `test_checkpoint_publication_atomic_and_checksummed`;
  `test_evaluation_rows_immutable`; `test_export_is_read_only`;
  `test_measurement_vs_proxy_labeling` (byte/param fields carry
  `measured|estimated` provenance);
  `test_protected_label_capability_boundary` — where a benchmark declares
  protected evaluation labels, search/selection code paths cannot read
  them (capability test, active from Phase 0 on the reference runner);
  `test_speciation_materially_affects_reproduction` — **contract defined
  now, activated with Topograph (WP-2.8)**; until it passes, no NEAT
  terminology in claims or docs.

**Phase 0 exit (contract evidence):** all WPs green; both CI lanes green;
contracts import in all Phase 0 packages and all seven Python B0 skeletons
(import-direction suite); the data-only `shared-benchmarks/` B0 skeleton passes
its layout and catalog-loader checks; integrity suite green including the
reference resume proof; Tier A packs load-validated. The integrity gate remains
**open-labeled** for engine-specific resume/speciation hooks until each
engine proves them — a placeholder can never represent engine integrity.


---

## Phase 1 — Contenders + Compare Core

**Objective:** the trust layer works before any evolutionary engine exists.
Spec: claude-spec/05, /06.

### Active Phase 1 implementation and verification

Implemented and locally verified through loading, fitting, transactional
recording, unchanged three-file exports and read-only Compare consumption.
The checked work packages below describe implemented, tested behavior;
integration requires both hosted lanes on #29/#30. Runtime receipt:
`governance/phase1-runtime-evidence.json`.
The four core runs took 118–213 seconds each; smoke took 41 seconds. The
336 fits completed without failed evaluations. Dashboard surfaces and filters
were checked on desktop and mobile using separate synthetic UI fixtures;
actual admission uses only the real Contenders exports.

- **Data/runtime:** retain all eight canonical IDs, legacy source parameters,
  split/dtype semantics and frozen metadata. An additive pinned runtime manifest
  binds source and reference-array hashes; Shared verifies actual consumed
  cache bytes. Tests cover legacy equality, altered bytes/versions, immutable
  cache reuse and seed-specific splits.
- **Contenders:** configurable dependency-light pools for all four groups,
  optional boosted/torch models with visible skips, isolated bounded fits,
  actual training telemetry and failed/invalid accounting. Test learning,
  train-only preprocessing, missing extras, timeout/failure counting and exports.
- **Compare:** file-only ingestion, exact case/budget/seed checks, honest lane
  states, required-floor audit, L0–L3 quality, append-only trends and complete
  dashboard surfaces. Test mismatches, missing data, ties/directions, cohort
  separation, rebuilding without reruns and interactive filters.
- **Verification/exit:** focused package and policy tests, both hosted lanes,
  real contenders-only `tier1_core@64`, low/mid repeat evidence as required by
  audit, complete dashboard and explained quality gaps. Individual checks/runs
  stay within 30 minutes; no multi-hour training campaign is started.

A reviewed metadata snapshot can remain `planned`/`catalog_only` while separate
runtime evidence proves loading. This does not silently promote the frozen
catalog. The smoke envelope @16 cannot fit all 25 minimum contenders and must
show incomplete floor coverage. No engine or scientific qualification follows
from the Phase 1 contract exit.

**Lane split & sync:** **A:** WP-1.1, 1.2 (Contenders package) + WP-1.7,
1.8 (Compare's read-only analyzers `audit.py`/`quality.py` — disjoint
modules from B's orchestration). **B:** WP-1.3, 1.4, 1.5, 1.6 (Compare
orchestration, trends, dashboard). **Joint:** phase-exit fair-matrix run.
*Interface freeze:* export contract (Phase 0, already frozen), pack/case
schema (B→A), adequacy-label enum (A→B for lane summaries).

- [x] **WP-1.1 Required contender floor — all four groups.** Tabular,
  synthetic, **image (flat-feature MLP/tree)**, and **language modeling
  (n-gram)** required pools per claude-spec/06 — implemented now even
  though image/LM packs arrive in Phase 4; exercised by fixture tasks
  until then. `evaluation_semantics` = one fit/eval pass per contender.
- [x] **WP-1.2 Optional enhanced contenders.** `boosted` + `torch` extras;
  skips recorded in exports, surfaced by Compare — never silent.
- [x] **WP-1.3 Pack resolution + case model.** Budget-stamped compare
  packs; case = (pack, budget, seed); workspace layout per claude-spec/05.
- [x] **WP-1.4 fair-matrix (contenders-only first).** Orchestration,
  export validation, budget parity, `lane_acceptance.json`, per-case
  summaries. **Complete lane-state vocabulary**: contract-fair /
  trusted-core / trusted-extended **plus explicit exploratory and
  reference states**, alongside accounting + repeatability states.
  Standing rule enforced in code: `--no-contenders` cohorts are stamped
  engine-only and can never support an external-floor claim.
- [x] **WP-1.5 Trend artifacts.** Per-case `trend_rows.json`; append-only
  workspace JSONL; trend markdown surfacing lane accounting +
  repeatability; `workspace-report` rebuild.
- [x] **WP-1.6 Dashboard — full Phase 1 contract.** Winner tables
  (full-system + projects-only), lane health by budget, per-seed
  snapshots, multi-seed spread/CIs **and pairwise seed deltas**, ceiling
  ties separated, **measurement downgrade reasons**, **backend/hardware
  filters**, **recent full-run history**, functioning Evidence Explorer
  (score-over-budget/case, benchmark/task-kind filters), and the **named
  decision slices** of claude-spec/05 (later decision-gate enforcement
  depends on them).
- [x] **WP-1.7 benchmark-audit with adequacy.** Pack admission audit incl.
  per-benchmark **floor adequacy labels** (`strong_floor`,
  `acceptable_floor`, `weak_floor`, `missing_enhanced_pressure`); a
  `weak_floor` blocks decision-grade promotion; full claude-spec/02
  admission surface (runtime class, cache validation, budget
  divisibility); decision-grade requires **zero blockers**.
- [x] **WP-1.8 output-quality.** L0–L3 classifier with per-run gap report
  (L4 in Phase 3).

**Phase 1 exit (contract evidence):** contenders-only fair-matrix at
`tier1_core@64` end-to-end `contract-fair`; commands:
`fair-matrix --workspace <ws>` then `workspace-report <ws>`,
`benchmark-audit --pack tier1_core` → passed/0 blockers,
`output-quality <ws>` → all runs ≥ L2 with explained gaps; dashboard
renders every required surface; Linux CI carries compare + contenders
checks.

---

## Phase 2 — Prism + Topograph

**Implemented and locally accepted (2026-09-07, #31; hosted checks gate merge):**

- **WP-2.1a / 2.5a — Search objects:** validated, deeply immutable genomes;
  content IDs; family compatibility and innovation-aligned graph operations.
  Verify every family/operator with a real optimizer update on both backends,
  plus invalid shapes, graph cycles, causal LM and STE gradient tests.
- **WP-2.2a / 2.6a / 2.7a — Training:** package-local differentiated MLX and
  NumPy models, AdamW, bounded epochs/time, train-only regression calibration,
  measured serialized bytes versus estimated packed precision bytes. Shared
  retains only numerical preprocessing and infrastructure. The optional Shared
  dataset extra preserves the exact Phase-1 loader/split bytes.
- **WP-2.3a / 2.8a — Selection and state:** family niches/Pareto and actual
  reproduction-changing speciation; domain mutation, adaptive scheduling,
  namespace-isolated inheritance. Serialize RNG, innovations, archives and
  normalization buffers. A historical archive best must survive a worse refit.
- **WP-2.4a / 2.9a — Run boundary:** engine-local coordinators, frozen Shared
  RunWorkspace/DuckDB/checkpoints, durable worker result before row commit,
  export snapshot ownership, idempotent recovery, source/config/data drift
  rejection. Test real SIGKILL after worker/result/row/stage/payload/manifest;
  earlier incomplete work must never be silently charged twice.
- **WP-2.10a — Exit evidence:** obligatory engine telemetry, Compare ingestion,
  report/model replay, explicit portability-only fallback, hosted Linux and
  macOS tests, three-seed core@64 and Tier-A cohort. Exact source commits, run IDs and verified artifact digests are recorded in
  `governance/phase2-runtime-evidence.json`.


**Objective:** reference engine and first challenger at L3 on Tier A
**and** `tier1_core@64`. Spec: claude-spec/07, /08 — scope claim: **ch. 08
minus QD-archive extras and minus full deployment objectives** (both land
in Phase 6; basics land here).

**Lane split & sync:** **A:** WP-2.1–2.4 (Prism, entire package). **B:**
WP-2.5–2.9 (Topograph, entire package). **Joint:** WP-2.10 (Compare
integration, telemetry conformance matrix, portability lanes) + exit
cohort. This is the cleanest split in the plan — the engines-never-import-
engines rule makes the lanes fully independent. *Interface freeze:*
export contract + budget accounting (Phase 0), Compare case orchestration
(Phase 1); no A↔B interfaces exist by design.

- [x] **WP-2.1 [epic] Prism genome + families + compiler.** Split at
  expansion ≥: (a) frozen `ModelGenome` + content-addressed ID +
  mutation/crossover unit tests; (b) family registry + compatibility
  matrix; (c) compiler + per-family compile tests.
- [x] **WP-2.2 Prism training runtime.** AdamW, cosine/constant + warmup,
  clipping, early stopping, wall-time caps, NaN detection, multi-fidelity,
  weight-inheritance cache (parent → family fallback → checkpoint;
  cross-family groups), regression scaling/calibration from shared.
- [x] **WP-2.3 [epic] Prism pipeline.** Split ≥: (a) seeding with family
  diversity + benchmark selection (undercovered bias); (b) archives
  (elites, Pareto, family niches); (c) reproduction (tournament, splice +
  uniform crossover, adaptive rate, domain-aware mutation incl. morphs);
  (d) resume + persistence + engine-specific
  `test_resume_equals_uninterrupted`.
- [x] **WP-2.4 Prism run boundary + CLI.** RunWorkspace-conformant
  directories; verbs evolve/inspect/report/benchmarks/warm-cache/
  symbiosis-export; tiny-smoke e2e test.
- [x] **WP-2.5 Topograph genome.** Layer/Connection (+Conv, expert,
  GateConfig) genes, innovation numbers, operator vocabulary, per-layer
  precision fields.
- [x] **WP-2.6 Topograph precision modules.** BitLinear (ternary/STE),
  QuantizedLinear (INT4/8); target-layer precision inheritance;
  measured-vs-estimated byte accounting.
- [x] **WP-2.7 Topograph compiler + training.** Graph-driven EvolvedModel,
  LayerNorm, Kaiming, AdamW + warmup-cosine + clip, Lamarckian
  WeightCache (exact/partial/none, 0.3/0.6 ratios, savings visible in
  accounting).
- [x] **WP-2.8 [epic] Topograph evolution loop.** Split ≥: (a) speciation
  by compatibility distance **materially affecting reproduction**
  (activates the integrity-gate speciation test — NEAT vocabulary allowed
  only after green); (b) phase scheduler explore/refine/polish + EMA
  operator scaling; (c) novelty scoring + blending (`novelty_weight`
  default 0 — ch. 08 search mechanic, **not** the QD archive; MAP-Elites
  is Phase 6); (d) per-benchmark elites + benchmark pooling; (e)
  memory-aware process-pool evaluator; (f) atomic scheduler-state
  checkpointing + engine resume test.
- [x] **WP-2.9 Topograph run boundary + CLI + hardware basics.** Verb set
  incl. `target_device` config surface and measured latency/bytes fields
  in exports (full deployment objectives + atlas: Phase 6); tiny-smoke
  e2e.
- [x] **WP-2.10 Integration, telemetry conformance, portability.** Both
  engines in fair-matrix; **telemetry conformance matrix** with golden
  tests per claude-spec/04 (Prism: family distribution/archive occupancy/
  inheritance usage; Topograph: topology size/novelty metrics/operator
  success; phase exits fail when mandatory telemetry is absent); macOS CI
  real; **Linux `numpy_fallback` lane per engine = compare-grade tiny
  execution**: real tiny search/eval, resume, report rebuild, symbiosis
  export, Compare ingestion — stamped `portability_only`, never mixed
  with `mlx_native` cohorts.

**Phase 2 exit (contract + exploratory-scientific evidence):** 3-seed
`trusted-core` cohort at `tier1_core@64`; **all systems L3 on Tier A and
`tier1_core@64`** (`output-quality` green on both lanes); integrity suite
incl. both engines' resume tests and the speciation test green; fallback
lanes green on Linux CI. Required hosted checks on #31 enforce these gates.

The recorded cohort provides all three core seeds and Tier-A L3 coverage.
Tier A currently reuses the core benchmark surface; it adds contract evidence,
not independent dataset breadth. Producer 1828b28 and consumer 7ece4af remain
separately bound. Current failure-path fixes have explicit regression evidence.
Snapshots retain full history within 256 proposals, with 128 MiB write guards;
this bounds acceptance work but does not claim scalable long-run persistence.

---

## Phase 3 — Evidence Registry + Statistical Layer

**Objective:** durable memory and decision-grade statistics.
Spec: claude-spec/12, /05.

**Lane split & sync:** **A:** WP-3.1 (registry) + WP-3.4 (registry-backed
dashboard, L4 classifier). **B:** WP-3.2 (report vocabularies) + WP-3.3
(statistical layer). **Joint:** WP-3.5 (decision-gate machine enforcement)
+ exit. *Interface freeze:* registry row schema (claude-spec/12 field set,
co-signed at phase start so B computes over rows A stores); the three
decision-label enums (B→A for dashboard display).

- [x] **WP-3.1 Evidence registry.** promote/validate; full row fields;
  immutability + supersession; compact artifact copies.
  **Standing CI gate from here on:**
  `evidence validate --registry evidence --require-artifacts` must be
  green before any registry citation merges.
- [x] **WP-3.2 Evidence report — distinct vocabularies.** Three separate
  enums with explicit mappings, never compressed: **cohort statistical
  labels** (`clear_gain`, `likely_gain`, `no_material_change`,
  `regression`, `inconclusive`, `needs_more_runs`); **aggregation labels**
  (`gain`, `no_material_change`, `inconclusive`, `blocked`); **PR
  decision categories** (`Tier 1 regression`, `needs more seeds`,
  `Tier B-only gain`, `regress`, `promote`, `inconclusive`, with the
  ch. 05 precedence). Minimum-seed gates (A:3, B:3/2, C:3/2, D:3).
- [x] **WP-3.3 [epic] Statistical layer.** Split ≥: (a) rank/score
  distributions + budget slopes + floor margins + ceiling-tie exclusion;
  (b) effect sizes + bootstrap CIs + **guarded non-parametric tests
  (Wilcoxon/Friedman-style, emitted only when unit counts permit, else
  `insufficient_data`)**; (c) synthetic fixtures (ceiling ties, missing
  runs, backend drift, mixed budgets); (d) **mandatory diagnostics**:
  transfer-proof state, LM-flatline detection, first-pass engine roles —
  each with explicit `not_applicable`/`insufficient_data`, never silent
  omission; (e) **runtime tradeoffs mandatory** in every
  advancement-ready group (wall-clock, evals/sec, sec/success, score/sec,
  family allocation).
- [x] **WP-3.4 Registry-backed dashboard history + L4 classifier.**
- [x] **WP-3.5 Decision-gate machine enforcement.** PR template **plus a
  CI policy checker** that parses the evidence block and validates:
  artifact paths exist in the registry, exact case/run IDs, named
  dashboard slices, lane states present, exactly one decision category.
  Single-plan policy test extended.

### Active Phase 3 implementation contract

**Requirements:** claude-spec/12 Evidence Registry, L4 Statistical Decision
Layer and mandatory diagnostics; /05 decision precedence and evidence bundle.
**Depends on / Produces / Blocks:** Phase 2 L3 exports; additive Compare-owned
registry schema v1, statistical reports and PR evidence validator; blocks
Phase 4 trusted-extended claims. Existing Phase 0 schemas remain unchanged.
**Hosts/backends:** Linux and macOS; reports preserve native/portability and
host distinctions. One implementation worker, two independent review agents.

- **WP-3.1a — Durable rows:** one immutable run record per label/run identity,
  with all chapter-12 fields and compact score/telemetry snapshots. Promotion
  reads verified exports and recomputes admission; user-supplied summaries
  cannot assert trust. An OS lock serializes writers; append-only index is the
  source of truth, checksummed manifest/report are recoverable derived views.
  Supersession appends an event and never rewrites the old row. Artifact
  publication precedes index commit; interrupted unreferenced copies are not
  evidence. Copy only bounded metadata, keep large models external with hashes.
- **WP-3.1b — Validation:** reject duplicate/conflicting identities, unsafe
  paths, incomplete index lines, stale hashes, missing required artifacts and
  unsupported schema fields. Stable labels identify explicitly selected
  before/after cohorts; compare does not infer cohorts from directory names.
- **WP-3.2a — Vocabulary:** separate strict statistical, aggregation and PR
  decision enums; enforce chapter-05 precedence and seed thresholds.
- **WP-3.3a — Descriptive evidence:** matched benchmark/seed score and rank
  distributions, floor margins, ceiling-tie exclusion, budget slopes and
  explicit missing/duplicate observations. Never pool incompatible budgets,
  backend versions, hosts or training policies. Before/after permits only
  explicitly identified source revisions to differ in the protocol binding.
- **WP-3.3b — Inference:** deterministic paired bootstrap over independent
  seed-level effects, bounded nonparametric tests with stated unit counts,
  effect sizes and uncertainty; insufficient counts remain inconclusive.
  Do not treat candidate outcomes or benchmark repeats as independent seeds.
- **WP-3.3c — Diagnostics:** always emit transfer readiness, LM flatlines,
  provisional engine roles, runtime tradeoffs and family allocation. Missing
  proof stays insufficient_data/not_applicable; no native-transfer inference.
- **WP-3.4a — Consumer:** registry-derived history, required named dashboard
  slices and L4 classification based on validated repeated evidence, not a
  caller-provided level. Keep best observed separate from advancement claims.
- **WP-3.5a — Enforcement:** structured PR evidence block, artifact/run/case
  validation and exactly one derived decision category; malformed fixture
  must fail. CI validates committed registry citations and the single plan.

**Tests first:** corrupt/stale/symlink artifacts, interrupted append/publication,
repeated promotion and supersession; ceiling ties, missing seeds, duplicate
runs, backend/host/policy drift and mixed budgets; false trust/promotion;
malformed PR blocks and escaped dashboard content.
**Verify:** `uv run --package evonn-compare pytest EvoNN-Compare/tests`;
`scripts/ci/compare-checks.sh`; `scripts/ci/b0-policy-checks.sh`; both hosted
lanes; `evonn-compare evidence validate --registry <registry> --require-artifacts`.
**Evidence:** fixture-based contract decisions plus a bounded real before/after
engine qualification; durable receipts cite exact source and consumer revisions.
**Failure conditions:** invalid artifacts, unpaired/confounded comparisons,
unsupported trust upgrades, missing required diagnostics or failing checks.

**Phase 3 exit (contract evidence):** a before/after engine change is
judged end-to-end from registry-backed evidence; the policy checker blocks
a deliberately malformed test PR; all Phase 3 validators green in CI.

---

## Phase 4 — Stratograph + Primordia

**Objective:** four-engine portfolio; Tier B online. Spec: claude-spec/09,
/10, /02. **Prerequisite (cumulative):** each new engine reaches L3 on
Tier A and `tier1_core@64` before its Tier B evidence counts.

**Lane split & sync:** **A:** WP-4.1–4.4 (Stratograph, entire package).
**B:** WP-4.5, 4.6 (Primordia, entire package) + WP-4.7 (Tier B catalog +
packs). **Joint:** WP-4.8 (integration, CLI conformance, telemetry rows)
+ exit cohort. *Interface freeze:* export/budget contracts (Phase 0),
catalog schema (Phase 0; B extends data, not schema), seed-candidate
artifact shape (B→Phase 5, co-signed here because Primordia emits it).

- [x] **WP-4.1 Stratograph genome + codec** (invariants, structural
  metrics, digesting).
- [x] **WP-4.2 Stratograph compiler + proxy evaluator** (cell reuse,
  trained heads, fidelity-regime labels).
- [x] **WP-4.3 Stratograph search ops** (clone/specialize/rewire/motif
  rewrite; crossover preserving macro edges; task/dimension seed
  profiles; crossover-first — no broad exploitation slot).
- [x] **WP-4.4 Ablation harness + motif mining** (flat/unshared/shared/
  no-clone/no-motif-bias; `motifs analyze`).
- [x] **WP-4.5 [epic] Primordia engine.** Split ≥: (a) primitive genome +
  mutation; (b) MLX lane + runtime caps (epoch/family caps, architecture
  clamps); (c) `numpy_fallback` compare-grade lane; (d) bounded
  elite/archive search + budget-matched scheduling.
- [x] **WP-4.6 Primordia artifacts — strict schemas.** Primitive bank
  (ranked, diversity descriptors), `seed_candidates.json`
  (benchmark-conditioned), `search_leaders.json`, usage/coverage/failure
  telemetry; **reconstruction test**: inspect rebuilds the bank view from
  `best_results.json`/`trial_records.json` when the bank artifact is
  missing. File existence is not completion; schema validity is.
- [ ] **WP-4.7 Tier B benchmarks + packs.** Catalog extension (OpenML,
  small image, real LM caches); `tier_b_core`, `tier_b_core_v2`
  (+cumulative); presets; **decision-grade audit with zero blockers and
  adequacy labels** (exact command in exit).
- [x] **WP-4.8 Integration + CLI conformance.** Both engines: full verb
  set with tiny-config e2e tests (evolve, resume, inspect, report,
  benchmarks/cache discovery, symbiosis export); engine-specific resume
  tests; telemetry conformance rows (Stratograph: macro depth/reuse/
  clone+specialize counts/motif frequency; Primordia: primitive counts/
  bank size/promotion counts); CI scripts in the Linux lane.

WP-4.7 data and `tier_b_tiny` are implemented and contract-qualified. The
2026-09-09 repeated 64/128 cohort passes decision-grade benchmark admission
with zero blockers. The follow-up provides 24 L4 contrasts. Its parent remains
open for the complete specified preset surface and trusted-extended exit; admission alone is not that exit. The other
checked work packages mean implemented + short-qualified; they do not close the
full scientific exit. Independent reviews covered numerical/search behavior,
artifact semantics, transport and the bounded command surface.

### Active Phase 4 implementation contract

**Requirements:** claude-spec/09 Genome, Compilation, Operators, Ablation,
Motif Mining and Diagnostics; /10 Search Lane, Artifacts and Standalone Rule;
/11 seed artifact contract; /02 benchmark ladder; /03 accounting and fidelity.
**Depends on / Produces / Blocks:** reviewed Phase 3 analysis interface; two
independent package runtimes and Shared seed-envelope v1; blocks the larger
five-system comparison campaign. Native transfer ingestion remains Phase 5.
**Hosts/backends:** bounded NumPy and native MLX candidate evaluation; native
proxy execution is labeled separately from end-to-end hierarchy training.

- **WP-4.1a — Hierarchy genome:** strict macro/cell DAGs, reachability and
  references, deterministic codec, macro/cell depth and reuse descriptors.
- **WP-4.2a — Executable hierarchy proxy:** shared compiled cell objects
  process their own macro inputs; deterministic projections depend on cell
  semantics, not arbitrary IDs. Fit a real GELU readout, with inherited trained
  head weights. Preserve clone function until specialization. Classification,
  regression, image and causal-LM interfaces expose honest proxy fidelity.
- **WP-4.3a — Hierarchy search:** crossover-first segment inheritance,
  clone/specialize/rewire/skip/width/activation/motif changes; explicit task and
  dimension seed profiles and budget-dependent depth limits. No broad
  benchmark-leader exploitation slot. Resumable lineage and occupied niches.
- **WP-4.4a — Ablation and motifs:** matched-budget flat/unshared/shared/
  no-clone/no-motif-bias variants; mine repeated sub-cell structures from actual
  winners with local/global and clone lineage. Report LM evaluator/genotype/
  compiler/search diagnostics with unavailable causes explicit.
- **WP-4.5a — Primitive genome:** tiny sparse/gated circuits, validated
  connectivity, merge and activation operators; package-local differentiable
  compiler, training, loader boundary and search. Record necessary copied
  infrastructure in the required compact duplication notes.
- **WP-4.5b — Cheap search:** explicit family/slot epoch caps, architecture
  clamps, cheaper mutations for weak/expensive parents using parameter count ×
  optimizer updates (measured seconds remain diagnostic), bounded elite archive,
  benchmark/family leaders and matched per-benchmark scheduling.
- **WP-4.6a — Exported bank:** strict Shared metadata envelope with local
  genotype encoding, source/data/split/cost/runtime provenance, checksums,
  descriptors, target compatibility and versioned ingestion instructions.
  Produce ranked bank, benchmark-conditioned seeds and search leaders;
  reconstruct a missing bank from durable best/trial artifacts. No claimed
  downstream influence or native transfer before Phase 5 proof.
- **WP-4.7a — Tier B data:** additive catalog/runtime definitions for real
  OpenML, small image and LM inputs; preserve existing IDs/splits. Add only
  packs/presets supported by bounded verified runtime. Keep inadequate floors
  and unqualified broader cohorts explicitly blocked.
- **WP-4.8a — Integration:** explicit worker module and loader callbacks,
  checksum-bound extra artifacts before export publication, complete Compare
  ledger/fidelity/telemetry validation for all four engines. Preserve historical
  bootstrap receipts while moving current probes to an honest contract role.

**Tests first:** invalid/cyclic/unreachable genomes; shared executor identity
and different inputs; clone equivalence then specialization; real nonzero
updates and head inheritance; deterministic resume and process-death fences;
all ablation variants; invalid/missing seed provenance and bank reconstruction;
unsupported task evidence never silently qualified; both native and portable
winner replay and CLI conformance.
**Verify:** package CI scripts; Shared foundation and import/governance checks;
short Tier-A/core@64 L3 qualification and shared-vs-flat ablation; both hosted
lanes. Each local qualification command stays below 30 minutes.
**Evidence:** compact runtime receipt and registry-bound contract decisions;
large model/data artifacts transported externally. Separate proxy, portability,
native runtime, scientific superiority and transfer evidence.
**Failure conditions:** engine coupling, proxy mislabeled end-to-end, missing
budget charges, unbound artifacts, false L3/L4 promotion or failing checks.
The Tier-B three-seed five-system 64/128 cohort is complete and analyzed in
the 2026-09-09 receipt. Further training requires a separate execution decision;
this analysis starts no additional fits.

**Phase 4 exit:** five-system-cohort Tier B `trusted-extended` at 3 seeds —
where `trusted-extended` requires **L4 repeated-seed aggregates, a
statistical decision label, complete contender floor, and validated
decision-grade artifacts** (not merely per-run L3); ablation harness
produces first shared-vs-flat evidence (exploratory-scientific);
`benchmark-audit --pack tier_b_core_v2` → passed, 0 blockers.

---

## Phase 5 — Native Transfer Proof

**Objective:** prove, refute, or classify the cumulative-search claim.
Spec: claude-spec/11. **"Native" is pinned to Topograph's real MLX
runtime** — `numpy_fallback` transfer runs are portability evidence only
and cannot support the claim.

**Lane split & sync:** **A:** WP-5.1, 5.2 (seed schema hardening,
Topograph native consumption). **B:** WP-5.3 (Compare transfer surfaces +
campaign manifest). **Joint:** WP-5.4 (the proof campaign itself — both
agents run and interpret it together). *Interface freeze:* seed artifact
contract (ch. 11 field set, co-signed at phase start; A validates it, B's
manifest checks it).

- [ ] **WP-5.1 Seed artifact schema hardening** (full ch. 11 contract;
  gating validator).
- [ ] **WP-5.2 Topograph native seed consumption.** `unseeded`/`seeded`/
  `staged_seeded` demonstrably changing initialization/search bias
  (asserted in tests); accounting modes free/reported/charged, default
  `reported_prior`.
- [ ] **WP-5.3 Compare transfer surfaces + campaign manifest.**
  `seeded-compare`, `transfer-regimes`; a **machine-validated campaign
  manifest** that rejects unmatched regime matrices — identical pack,
  budget, seed, backend class, and contender context across regimes is an
  automated acceptance rule, not prose; full runtime metadata recorded;
  portable-vs-native proof state in registry rows.
- [ ] **WP-5.4 Proof campaign — exact sequence + explicit bar.**
  `tier_b_core_v2@96` × 3 seeds → `@384` × 2 seeds if signal →
  **`tier_c_architecture_sensitive@128`, exploratory only** (in-sequence,
  per ch. 11). Outcome classes: `regression`, `no_gain`, `inconclusive`,
  **`provisional_gain_reported_prior`** (valid research signal, not a
  budget-matched success), and **`gain` — only after replication under
  `charged_prior`** with matched pack/budget/seed/backend/contender
  context. Positive-gain bar encoded from the S3 template: ≥ 5% relative
  improvement on the declared metric, surviving both baselines (unseeded
  control and contender floor unchanged), with clean attribution.
  Failure attribution recorded (seed quality vs ingestion vs benchmark
  mismatch vs accounting).

**Phase 5 exit (decision-grade-scientific evidence):** one auditable
native transfer outcome in the registry with repeated evidence and one of
the five explicit classifications; `evidence validate --require-artifacts`
green.

---

## Phase 6 — QD, Portfolio Decisions, Tier Hardening, L-SCI

**Objective:** evidence-backed roles and the Lab's scientific conclusion.
Spec: claude-spec/14, /12, /02, /08 (deferred scope).

**Lane split & sync:** **A:** WP-6.1, 6.2 (descriptors, MAP-Elites,
Topograph deferred hardware scope, pre-registered QD experiment). **B:**
WP-6.3, 6.4 (Stratograph LM diagnostic, tier hardening). **Joint:**
WP-6.5 (portfolio statuses) + WP-6.6 (L-SCI — both agents co-own the
evidence matrix and the closure decision). *Interface freeze:* descriptor
schema (A→Compare reporting), tier gate definitions (B→joint exit).

- [ ] **WP-6.1 Descriptor schema + archives.** Shared optional descriptor
  schema; Topograph descriptor exports; **MAP-Elites archive lands here**
  (moved from Phase 2); Compare archive report (occupancy, fill ratio,
  per-cell improvement, Pareto/diversity views). Topograph deferred
  hardware scope lands here too: deployment objectives
  (latency/memory/throughput proxies) and atlas-style reporting.
- [ ] **WP-6.2 Pre-registered QD experiment.** Registered **before**
  execution: same-engine QD-disabled control; identical packs, seeds,
  backend, evaluation policy; descriptor definitions + bins; diversity
  improvement threshold; allowed quality-loss/non-inferiority margin;
  repeated seeds per the tier gate. Promote only if the pre-registered
  thresholds are met.
- [ ] **WP-6.3 Stratograph LM-flatline diagnostic** (evaluator vs
  genotype vs compiler vs policy attribution) + hierarchy ablation
  evidence.
- [ ] **WP-6.4 [epic] Tier hardening.** Split ≥: (a) Tier C packs +
  **cumulative** gates: benchmark-admission hardening (two clean 512, one
  clean 1024) **plus** ch. 12 seed gates (3 local-budget, 2 overnight
  seeds) — both required, never alternatives; (b) Tier D admitted broad
  lane with **its own separate leaderboard**, no broader claims until
  three clean repeated runs; (c) Tier E candidate audit file (admission
  reports only); (d) runtime-envelope probes (1 seed × 1 budget) —
  **stamped exploratory + backend/host-locked, non-promotable**.
- [ ] **WP-6.5 Portfolio status assignment.** Status-change validator
  **requires engine-only cohorts** for portfolio/parity decisions
  (contender-including cohorts reserved for external claims); every
  engine gets an evidence-backed status with registry links.
- [ ] **WP-6.6 Gate L-SCI — fixed evidence matrix (defined before the
  campaign runs).**
  **Positive closure requires** a promoted **contender-including** cohort
  that: passes the tier seed gate; has a qualified non-weak floor
  (adequacy labels); excludes ceiling ties from superiority evidence;
  reports effect sizes, uncertainty, runtime tradeoffs, and exact claim
  scope; carries an L4 decision-grade label; and passes
  `evidence validate --require-artifacts`.
  **Negative closure requires** the same predefined coverage and
  repeated-run completeness, then an evidence-backed conclusion that no
  engine clears the floor on the declared claim surface, with portfolio
  consequences recorded.
  `blocked`, `needs_more_runs`, and unresolved coverage gaps keep L-SCI
  **open** — an underpowered campaign can never become the negative
  conclusion.

**Phase 6 exit (decision-grade-scientific evidence):** L-SCI closed
positively or negatively per the matrix; engine roles evidence-backed;
Tier C promoted or explicitly exploratory with named blockers.

---

## Phase 7 — Performance Frontier, Observatory, Automation

**Objective:** sustainable operation. Spec: claude-spec/13, /15, /17.

**Lane split & sync:** **A:** WP-7.1, 7.2 (performance workflow +
optimization slices). **B:** WP-7.3, 7.4 (Observatory + automation loop).
**Joint:** WP-7.5 (release governance + conformance statement) + exit.
*Interface freeze:* performance-bundle schema (A→B for Observatory
display), reporting JSON surfaces (Phases 1/3, already frozen).

- [ ] **WP-7.1 performance-baseline workflow — full measurement set.**
  Wall-clock, candidates evaluated, valid/invalid ratio, cache hit rate,
  evals/sec, seconds/success, backend vs orchestration time,
  per-benchmark latency, peak memory, family allocation, metric-quality
  delta, contender-floor margin delta; exclusion reasons; bundles under
  `performance_baselines/<stamp>-<sha>/`.
- [ ] **WP-7.2 Optimization slices — prescribed matrix.** Each branch:
  Tier A @ 16 & 64, Tier B @ 96 & 384, one Tier C local run if
  compiler/evaluator/runtime logic changed, ≥ 2 seeds if search behavior
  changed, backend + host fingerprint recorded; baseline → one change →
  identical remeasure → accept/scrap/inconclusive with before/after
  artifacts.
- [ ] **WP-7.3 Observatory — acceptance-tested.** FastAPI + Jinja2 +
  Chart.js read-only app per claude-spec/15; acceptance tests for:
  scanner cadence + JSON-only ingestion (no markdown scraping), all
  required pages, mandatory plain-language info banners, filtering,
  variance display, decision-grade labeling, read-only guarantee.
- [ ] **WP-7.4 Automation loop — evidence-based gate.** Tiny-budget
  trend-detection configs; recurring bounded smoke + tiny compare;
  defined cadence; gate = **minimum row counts** (≥ N successful and the
  failure-classification path exercised) **and** every appended row
  classified improvement/regression/no-change — elapsed time alone never
  closes the gate.
- [ ] **WP-7.5 Release governance.** Package versions + changelogs;
  artifact compatibility policy + support windows; **Lab conformance
  statement** naming implemented spec versions; reproducible installation
  instructions; tagged release artifacts.

**Phase 7 exit (contract + producer-conformance groundwork):** one full
optimization accept/scrap cycle with artifacts; Observatory acceptance
suite green; automation gate closed on evidence counts; first conformance
statement published.

---

## Interop Producer Workstream (parallel, from Phase 3)

**Objective:** Gates I0 and I1. Spec: claude-spec/19, claudex-spec/19,
PROGRAM_CHARTER Workstream C. Standing rule: see Interop authorization
rule (Definitions) — I1 alone never authorizes real Product influence.

**Lane split & sync:** runs alongside Phases 3–7 as capacity allows.
**A:** WP-I.1, I.2 (versioning, dossier schema). **B:** WP-I.3, I.4
(fixtures, producer conformance suite). **Joint:** WP-I.5 (reverse-dossier
ingestion) + Gates I0/I1 evaluation. *Interface freeze:* dossier +
provenance-envelope schema (A→B, co-signed before fixture work starts).

| Gate | Lab-plan meaning (executable) |
|---|---|
| **I0** | Versioned export/import schemas published with changelogs; fixture corpus (valid, invalid, corrupt, old-version) exists with a fixture manifest |
| **I1** | Producer conformance: fixtures **and** at least one real runtime-produced artifact from each of the five export surfaces pass the producer suite |
| **I2** | Consumer conformance — Product-owned; not closable by this plan |
| **I3** | First real import registered end-to-end; requires I1 **and** I2 |

- [ ] **WP-I.1 Contract versioning with consumer semantics.** Semantic
  versions + changelogs for export contract, seed schema, canonical ID
  registry — **append-only history, immutable field meaning, major bumps
  for breaking changes, declared compatibility ranges, supersession
  metadata** (what Product staleness rules key on).
- [ ] **WP-I.2 Mechanism-dossier schema + validator + provenance
  envelope.** Schema carries everything a Product import dossier needs:
  source envelope (Lab spec version, commit, digests), claim +
  magnitude + scope, evidence registry labels + case/run IDs, risks,
  license/provenance, **negative results and scope limits as schema-level
  fields**; worked examples incl. one negative-result dossier;
  completeness machine-validated.
- [ ] **WP-I.3 Golden fixtures + fixture manifest.** Valid, invalid,
  corrupt, and old-version fixtures for every export surface; the
  manifest specifies **expected accept/reject/stale behavior and expected
  loss labels** per fixture.
- [ ] **WP-I.4 Producer conformance suite (Gate I1).** Validates schema +
  digest + provenance for fixtures **and** real runtime-produced
  artifacts from all five surfaces (benchmarks/packs, seed artifacts,
  mechanism dossiers, evidence rows, engine graduation bundles).
- [ ] **WP-I.5 Reverse-dossier ingestion.** Validated reverse-record
  schemas for **all four classes** (defect findings, backend
  qualification, statistical-protocol improvements, failed-adoption
  reports) preserving Product provenance; formal promotion into the
  hard-remainder backlog with the ch. 18 fields (owner, validation lane,
  acceptance criteria, expected evidence artifact).

---
