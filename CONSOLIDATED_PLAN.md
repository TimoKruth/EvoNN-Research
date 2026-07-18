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

# EvoNN Lab (claude-spec) — Master Execution Plan

**Revision:** 2 (integrates `archive/2026-07-17-LAB_PLAN_CRITIQUE.md`; status was `REVISE_BEFORE_BOOTSTRAP`, now revised)

> **For agentic workers:** This is the master plan for building the Lab. At
> the Lab repository it is installed as `CONSOLIDATED_PLAN.md` — the single
> active execution plan. **WP expansion never creates separate plan
> files:** expand the active WP either as a nested checklist section inside
> `CONSOLIDATED_PLAN.md` (replacing its summary while active) or as a
> PR-local checklist citing the WP. Completed checklists move to research
> logs, marked non-authoritative. A CI policy test fails if any other file
> declares itself an active execution plan.

**Goal:** Build the claude-spec research platform — four distinct search
engines, a trust substrate, and an evidence loop — to the point where Gate
L-SCI (scientific conclusion) and Gate I1 (interop producer conformance)
are both reachable.

**Architecture:** uv workspace monorepo; engines as independent packages
exchanging file artifacts; Compare as orchestrator/auditor; per-run DuckDB;
`mlx_native` scientific path with `numpy_fallback` portability path.
Normative source: `claude-spec/` chapters 00–19 **at the pinned revision
(Gate B0)**. Where this plan and the spec disagree, the spec wins.

**Tech Stack:** Python ≥ 3.13, uv workspace, Pydantic 2 (strict at
boundaries), MLX (macOS), NumPy (fallback), DuckDB (per-run), Typer,
pytest + ruff, scikit-learn (contender floor). Each non-normative choice is
labeled `accepted` (spec-mandated), `provisional` (default, replaceable),
or `spike-gated` (needs a validation spike before freeze). MLX wheel
availability on the pinned Python is `spike-gated`; all else here is
`accepted` per claude-spec/01.

## Definitions Used Throughout

- **five-system cohort** = the four engines + Contenders in one fair-matrix
  case set (distinct from the dashboard's full-system vs projects-only
  *views*).
- **Backend labels** — `mlx_native` (scientific evidence for engine
  training claims), `numpy_fallback` (portability evidence only,
  `portability_only` in cohort labels), `sklearn_contender`. Fallback
  results never mix silently with `mlx_native` cohorts.
- **Evidence classes** — every phase exit states which it produced:
  `contract`, `exploratory-scientific`, `portability`,
  `decision-grade-scientific`, or `producer-conformance` evidence.
- **Cumulative gates rule** — later gates include all earlier standing
  gates. Benchmark admission, output quality, seed coverage, backend
  qualification, artifact validation, and contender adequacy are cumulative
  requirements; satisfying one never substitutes for another.
- **Interop authorization rule** — I1 proves only Lab publishing readiness.
  No real artifact may influence Product behavior until consumer
  conformance (I2, Product-owned) passes; the first real crossing is
  recorded as I3.

## Global Constraints

- Python ≥ 3.13; one uv workspace lock at repo root (claude-spec/01).
- Engines MUST NOT import each other; Compare invokes engine CLIs and reads
  exports only; import-direction policy tests enforce this from Gate B0.
- `evonn_shared` stays dependency-light: no search logic, no genomes, no
  engine runtime (claude-spec/01).
- Canonical benchmark IDs only at every export boundary (claude-spec/02).
- Budget accounting fields on every compare-visible export
  (claude-spec/03): `evaluation_count`, `actual_evaluations`,
  `cached_evaluations`, `failed_evaluations`, `invalid_evaluations`,
  `resumed_from_run_id`, `resumed_evaluations`, `partial_run`,
  `evaluation_semantics`. Validators enforce
  `actual_evaluations ≤ evaluation_count` for **all** runs (no partial-run
  exemption — there is no overrun license); `partial_run = true` whenever
  execution stopped before the declared envelope; accounting identities
  reject negative, inconsistent, or double-counted resumed/cached work.
- One DuckDB writer per file, per-run DBs only.
- Canonical run directory (`config.yaml`, `metrics.duckdb`, `state.json`,
  `summary.json`, `report.md`, `checkpoints/`) is validated by a
  `RunWorkspace` constructor/validator, not asserted by convention.
- Output-quality ladder L0–L4 (claude-spec/04); **standing requirement:
  every engine holds L3 on Tier A and `tier1_core@64`** before any trusted
  claim (claude-spec/04).
- Branch/PR policy per claude-spec/18; engine-advancement PRs carry the
  decision-gate bundle, machine-checked (WP-3.5).
- Foundation Integrity Gate (WP-0.10) is a permanent CI gate.
- New feature flags default off-or-better-default, prior behavior
  restorable (claude-spec/18).

## WP Template (mandatory at expansion)

Every WP expands using this template before implementation:

```markdown
### WP-X.Y — Outcome-oriented title
**Requirements:** exact spec sections (e.g. claude-spec/04 §Export Contract)
**Depends on / Produces / Blocks:** WP IDs; stable interfaces + artifact paths
**Hosts/backends:** required execution classes
**Tests first:** named test files/cases
**Verify:** exact commands and expected results
**Evidence:** machine-readable artifact proving completion + its class
**Failure conditions:** what keeps this WP open
```

WPs marked **[epic]** below MUST be split into template-conforming sub-WPs
inside the consolidated plan at expansion; the split is part of the WP.

## Parallel Execution Model (Two Lanes)

The plan is executed by **two parallel agents — Lane A and Lane B** — with
a joint integration step closing every phase. Each phase declares its lane
split in a **Lane split & sync** block; WPs not listed there are joint.

Rules:

1. **Ownership.** A lane touches only its assigned packages for the phase.
   Two lanes may share a package only on the explicitly listed disjoint
   modules. File-collision between lanes inside a phase is a process
   defect, not a merge problem to absorb.
2. **Interface freeze.** At phase start both agents co-sign the phase's
   interface contract — the types, CLI shapes, and artifact schemas that
   cross the lane boundary (each phase's freeze list is in its sync
   block). Changing a frozen interface mid-phase requires a joint
   mini-review recorded in the consolidated plan.
3. **Branching.** Each lane works on `agent/p<N>-lane-<a|b>-<slug>`;
   integration happens on `agent/p<N>-integrate`.
4. **Cross-review.** Each lane's phase work merges only via a PR reviewed
   by the *other* lane's agent, checked against the pinned spec chapters,
   the WP requirements, and the integrity suite — the reviewing agent is
   accountable for the review, not just a rubber stamp.
5. **Joint integration WP.** After both cross-reviews: merge both branches
   into the integration branch; run full CI on both hosts, the integrity
   suite, all cross-cutting suites (import-direction, telemetry
   conformance where applicable), and the phase-exit acceptance commands;
   fix integration defects pairwise; only then evaluate the phase exit
   gate. The phase exit is always a joint decision.
6. **Fallback.** If only one agent is available, lanes execute
   sequentially A-then-B with self-review replaced by the normal PR flow;
   the integration WP still runs unchanged.

## Phase Map And Dependencies

```
B0 ─► Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─► Phase 4 ─► Phase 5 ─► Phase 6 ─► Phase 7
(pin) (contracts (floor+    (Prism,    (evidence  (Strato,   (transfer  (QD, tiers, (perf, Obs,
       +integrity) Compare)  Topograph) +stats)    Primordia)  proof)     L-SCI)      automation)
                                          │
                                          └──► Interop Producer Workstream (WP-I.*, parallel from Phase 3; Gates I0/I1)
```

Cross-phase dependency notes (enforced via `Depends on` at expansion):
benchmark audits depend on contender adequacy labels (WP-1.1 → WP-1.7);
dashboard decision slices depend on stable case/evidence schemas
(WP-1.4/3.1 → WP-1.6); native transfer depends on registry promotion and
backend classification (WP-3.1, WP-2.10 → Phase 5); I1 fixtures depend on
export schemas (WP-0.2 → WP-I.3); Observatory depends on structured JSON
from all reporting surfaces (Phases 1/3 → WP-7.3).

---

## Gate B0 — Reproducible Authority And Repository Bootstrap

- [x] **B0.1** Lab repository created; work starts on an implementation
  branch, never `main`. Local evidence: work is on `agent/b0-bootstrap`.
- [ ] **B0.2** Governing sources pinned with a checked-in provenance
  manifest (upstream URL, exact commit, declared spec version, import
  date, tree digest) — commit-pinned submodule or subtree preferred:
  `claude-spec/` (full), `PROGRAM_CHARTER.md`, and
  `claudex-spec/19-research-interop.md` (consumer acceptance is governed
  by the Product chapter, not by Lab documents). A recorded procedure
  defines how spec upgrades are reviewed and reflected in traceability.
  **Open blocker:** `authoritative_remote_url_absent`; the current pin is
  truthful local-only/provisional authority with null upstream URLs.
- [x] **B0.3** seven importable Python package skeletons (Shared,
  Contenders, Compare, Prism, Topograph, Stratograph, Primordia), each with
  an importable module, empty test, and per-package check script; plus
  one tested data-only `shared-benchmarks/` skeleton with an independently
  invocable dedicated check script (`scripts/ci/benchmarks-checks.sh`).
  Benchmark resolution helpers live in `evonn_shared.benchmarks`;
  `shared-benchmarks/` is not a Python package. Local package/data checks pass.
- [x] **B0.4** Import-direction policy tests green across all seven Python
  skeletons (engine↛engine, shared↛engines). The data-only
  `shared-benchmarks/` skeleton is layout- and catalog-loader-validated, not
  import-validated. The permanent policy validator passes locally.
- [ ] **B0.5** Both CI hosts execute real (non-stub) no-op workflows:
  Linux trust lane and macOS engine lane; Linux install proves MLX is
  platform-conditional; CI fixture artifacts carry exact host/runtime
  metadata; skeletons declare backend-capability manifests.
  **Open blocker:** `hosted_ci_not_executed`; workflow contracts and local
  bootstrap probes pass, but no hosted runs or uploaded artifacts exist.
- [x] **B0.6** Single-active-plan policy test green; the consolidated plan
  remains the sole active execution plan.

**Lane split & sync:** B0 is executed **jointly** (it is small and creates
the shared ground both lanes stand on).

**Exit (contract evidence):** Gate B0 exit remains open; Phase 0 cannot begin.
B0.2 and B0.5 must both close, then joint integration must pass on the hosted
Linux and macOS evidence before the Phase 0 interfaces are frozen.

---

## Phase 0 — Workspace, Contracts, Integrity Foundation

**Objective:** validated contracts, benchmark resolution, and the integrity
gate proven against executable skeletons. Spec: claude-spec/01–04, /13, /18.

**Lane split & sync:** **A:** WP-0.2, 0.3, 0.4, 0.5 (contract/budget/
telemetry models, identity + RNG). **B:** WP-0.1, 0.6, 0.7, 0.8, 0.9
(tooling/CI, checkpoints, RunStore/RunWorkspace, benchmarks, LM cache).
**Joint:** WP-0.10 integrity gate (consumes both lanes) + phase exit.
*Interface freeze:* canonical-encoding/digest API (A→B for checkpoint
checksums), export model shapes (A→B for RunWorkspace fixtures), catalog
loader signatures (B→A for validators).

- [ ] **WP-0.1 Workspace tooling.** Root workspace config, ruff/pytest
  config, `scripts/ci/*-checks.sh` per package wired into the B0 CI lanes.
- [ ] **WP-0.2 Export contract — all three files.** Strict models +
  round-trip writers/readers for `manifest.json`, `results.json`,
  `summary.json` with the complete claude-spec/04 surface (results incl.
  `task_kind`, memory, per-benchmark evaluation counts; manifest runtime
  block; summary budget echo + fairness flags + artifact digests).
  Valid/invalid fixtures covering unsupported/skipped visibility and
  schema-version compatibility.
  *Interfaces:* `Manifest|Results|RunSummary.model_validate_json`,
  `write_export(dir, m, r, s) -> ExportDigests`.
- [ ] **WP-0.3 Budget models.** `BudgetDeclaration` (7 contract fields) +
  `BudgetAccounting` (9 accounting fields incl. `resumed_evaluations`)
  with the corrected validators from Global Constraints.
- [ ] **WP-0.4 Telemetry + seeding models.** Envelope floor; 9 seeding
  fields with explicit-`unknown` semantics; ladder enum none|direct|staged.
- [ ] **WP-0.5 Identity + RNG streams.** Content digests over a **defined
  canonical encoding** (documented map ordering, float formatting, Unicode
  normalization, no absolute paths/timestamps in hash domain, schema
  version bound into the hash; cross-process golden vectors);
  digest-field-omitted rule. `derive_stream(root_seed, name)` for the
  named streams (search, data, split, init, order, augmentation, mutation,
  benchmark_sampling, worker, stats) — deterministic, scheduling-independent.
- [ ] **WP-0.6 Atomic checkpoints.** Stage → fsync payload → checksum →
  atomic rename → **fsync containing directory** → atomic manifest update
  referencing previous checkpoint digest. Crash tests at every transition
  (after payload rename; before/after manifest replacement); previous
  checkpoint stays authoritative until manifest commit.
- [ ] **WP-0.7 RunStore + RunWorkspace.** Per-run DuckDB schema (runs,
  append-only evaluations, artifacts, metadata). Single-writer ownership
  via OS advisory lock + lock record (process start identity + host
  fingerprint), stale-lock recovery semantics, crash/restart tests — PID
  alone is not ownership. `RunWorkspace` creates/validates the full
  canonical run directory; end-to-end fixture builds one, rebuilds
  `report.md`, and verifies artifact references without mutating evidence.
- [ ] **WP-0.8 Benchmark catalog + packs.** YAML schema per claude-spec/02
  (explicit direction, ceiling semantics, required contenders, runtime
  class); loaders; the 8 `tier1_core` benchmarks + smoke variants; packs
  `tier1_core`, `tier1_core_smoke`, `tier_a_contract`; append-only
  canonical ID registry.
- [ ] **WP-0.9 LM cache validation.** Existence/size/checksum for
  byte-level LM caches (used from Phase 4).
- [ ] **WP-0.10 Foundation Integrity Gate.** Permanent CI suite:
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

**Lane split & sync:** **A:** WP-1.1, 1.2 (Contenders package) + WP-1.7,
1.8 (Compare's read-only analyzers `audit.py`/`quality.py` — disjoint
modules from B's orchestration). **B:** WP-1.3, 1.4, 1.5, 1.6 (Compare
orchestration, trends, dashboard). **Joint:** phase-exit fair-matrix run.
*Interface freeze:* export contract (Phase 0, already frozen), pack/case
schema (B→A), adequacy-label enum (A→B for lane summaries).

- [ ] **WP-1.1 Required contender floor — all four groups.** Tabular,
  synthetic, **image (flat-feature MLP/tree)**, and **language modeling
  (n-gram)** required pools per claude-spec/06 — implemented now even
  though image/LM packs arrive in Phase 4; exercised by fixture tasks
  until then. `evaluation_semantics` = one fit/eval pass per contender.
- [ ] **WP-1.2 Optional enhanced contenders.** `boosted` + `torch` extras;
  skips recorded in exports, surfaced by Compare — never silent.
- [ ] **WP-1.3 Pack resolution + case model.** Budget-stamped compare
  packs; case = (pack, budget, seed); workspace layout per claude-spec/05.
- [ ] **WP-1.4 fair-matrix (contenders-only first).** Orchestration,
  export validation, budget parity, `lane_acceptance.json`, per-case
  summaries. **Complete lane-state vocabulary**: contract-fair /
  trusted-core / trusted-extended **plus explicit exploratory and
  reference states**, alongside accounting + repeatability states.
  Standing rule enforced in code: `--no-contenders` cohorts are stamped
  engine-only and can never support an external-floor claim.
- [ ] **WP-1.5 Trend artifacts.** Per-case `trend_rows.json`; append-only
  workspace JSONL; trend markdown surfacing lane accounting +
  repeatability; `workspace-report` rebuild.
- [ ] **WP-1.6 Dashboard — full Phase 1 contract.** Winner tables
  (full-system + projects-only), lane health by budget, per-seed
  snapshots, multi-seed spread/CIs **and pairwise seed deltas**, ceiling
  ties separated, **measurement downgrade reasons**, **backend/hardware
  filters**, **recent full-run history**, functioning Evidence Explorer
  (score-over-budget/case, benchmark/task-kind filters), and the **named
  decision slices** of claude-spec/05 (later decision-gate enforcement
  depends on them).
- [ ] **WP-1.7 benchmark-audit with adequacy.** Pack admission audit incl.
  per-benchmark **floor adequacy labels** (`strong_floor`,
  `acceptable_floor`, `weak_floor`, `missing_enhanced_pressure`); a
  `weak_floor` blocks decision-grade promotion; full claude-spec/02
  admission surface (runtime class, cache validation, budget
  divisibility); decision-grade requires **zero blockers**.
- [ ] **WP-1.8 output-quality.** L0–L3 classifier with per-run gap report
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

- [ ] **WP-2.1 [epic] Prism genome + families + compiler.** Split at
  expansion ≥: (a) frozen `ModelGenome` + content-addressed ID +
  mutation/crossover unit tests; (b) family registry + compatibility
  matrix; (c) compiler + per-family compile tests.
- [ ] **WP-2.2 Prism training runtime.** AdamW, cosine/constant + warmup,
  clipping, early stopping, wall-time caps, NaN detection, multi-fidelity,
  weight-inheritance cache (parent → family fallback → checkpoint;
  cross-family groups), regression scaling/calibration from shared.
- [ ] **WP-2.3 [epic] Prism pipeline.** Split ≥: (a) seeding with family
  diversity + benchmark selection (undercovered bias); (b) archives
  (elites, Pareto, family niches); (c) reproduction (tournament, splice +
  uniform crossover, adaptive rate, domain-aware mutation incl. morphs);
  (d) resume + persistence + engine-specific
  `test_resume_equals_uninterrupted`.
- [ ] **WP-2.4 Prism run boundary + CLI.** RunWorkspace-conformant
  directories; verbs evolve/inspect/report/benchmarks/warm-cache/
  symbiosis-export; tiny-smoke e2e test.
- [ ] **WP-2.5 Topograph genome.** Layer/Connection (+Conv, expert,
  GateConfig) genes, innovation numbers, operator vocabulary, per-layer
  precision fields.
- [ ] **WP-2.6 Topograph precision modules.** BitLinear (ternary/STE),
  QuantizedLinear (INT4/8); target-layer precision inheritance;
  measured-vs-estimated byte accounting.
- [ ] **WP-2.7 Topograph compiler + training.** Graph-driven EvolvedModel,
  LayerNorm, Kaiming, AdamW + warmup-cosine + clip, Lamarckian
  WeightCache (exact/partial/none, 0.3/0.6 ratios, savings visible in
  accounting).
- [ ] **WP-2.8 [epic] Topograph evolution loop.** Split ≥: (a) speciation
  by compatibility distance **materially affecting reproduction**
  (activates the integrity-gate speciation test — NEAT vocabulary allowed
  only after green); (b) phase scheduler explore/refine/polish + EMA
  operator scaling; (c) novelty scoring + blending (`novelty_weight`
  default 0 — ch. 08 search mechanic, **not** the QD archive; MAP-Elites
  is Phase 6); (d) per-benchmark elites + benchmark pooling; (e)
  memory-aware process-pool evaluator; (f) atomic scheduler-state
  checkpointing + engine resume test.
- [ ] **WP-2.9 Topograph run boundary + CLI + hardware basics.** Verb set
  incl. `target_device` config surface and measured latency/bytes fields
  in exports (full deployment objectives + atlas: Phase 6); tiny-smoke
  e2e.
- [ ] **WP-2.10 Integration, telemetry conformance, portability.** Both
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
lanes green on Linux CI.

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

- [ ] **WP-3.1 Evidence registry.** promote/validate; full row fields;
  immutability + supersession; compact artifact copies.
  **Standing CI gate from here on:**
  `evidence validate --registry evidence --require-artifacts` must be
  green before any registry citation merges.
- [ ] **WP-3.2 Evidence report — distinct vocabularies.** Three separate
  enums with explicit mappings, never compressed: **cohort statistical
  labels** (`clear_gain`, `likely_gain`, `no_material_change`,
  `regression`, `inconclusive`, `needs_more_runs`); **aggregation labels**
  (`gain`, `no_material_change`, `inconclusive`, `blocked`); **PR
  decision categories** (`Tier 1 regression`, `needs more seeds`,
  `Tier B-only gain`, `regress`, `promote`, `inconclusive`, with the
  ch. 05 precedence). Minimum-seed gates (A:3, B:3/2, C:3/2, D:3).
- [ ] **WP-3.3 [epic] Statistical layer.** Split ≥: (a) rank/score
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
- [ ] **WP-3.4 Registry-backed dashboard history + L4 classifier.**
- [ ] **WP-3.5 Decision-gate machine enforcement.** PR template **plus a
  CI policy checker** that parses the evidence block and validates:
  artifact paths exist in the registry, exact case/run IDs, named
  dashboard slices, lane states present, exactly one decision category.
  Single-plan policy test extended.

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

- [ ] **WP-4.1 Stratograph genome + codec** (invariants, structural
  metrics, digesting).
- [ ] **WP-4.2 Stratograph compiler + proxy evaluator** (cell reuse,
  trained heads, fidelity-regime labels).
- [ ] **WP-4.3 Stratograph search ops** (clone/specialize/rewire/motif
  rewrite; crossover preserving macro edges; task/dimension seed
  profiles; crossover-first — no broad exploitation slot).
- [ ] **WP-4.4 Ablation harness + motif mining** (flat/unshared/shared/
  no-clone/no-motif-bias; `motifs analyze`).
- [ ] **WP-4.5 [epic] Primordia engine.** Split ≥: (a) primitive genome +
  mutation; (b) MLX lane + runtime caps (epoch/family caps, architecture
  clamps); (c) `numpy_fallback` compare-grade lane; (d) bounded
  elite/archive search + budget-matched scheduling.
- [ ] **WP-4.6 Primordia artifacts — strict schemas.** Primitive bank
  (ranked, diversity descriptors), `seed_candidates.json`
  (benchmark-conditioned), `search_leaders.json`, usage/coverage/failure
  telemetry; **reconstruction test**: inspect rebuilds the bank view from
  `best_results.json`/`trial_records.json` when the bank artifact is
  missing. File existence is not completion; schema validity is.
- [ ] **WP-4.7 Tier B benchmarks + packs.** Catalog extension (OpenML,
  small image, real LM caches); `tier_b_core`, `tier_b_core_v2`
  (+cumulative); presets; **decision-grade audit with zero blockers and
  adequacy labels** (exact command in exit).
- [ ] **WP-4.8 Integration + CLI conformance.** Both engines: full verb
  set with tiny-config e2e tests (evolve, resume, inspect, report,
  benchmarks/cache discovery, symbiosis export); engine-specific resume
  tests; telemetry conformance rows (Stratograph: macro depth/reuse/
  clone+specialize counts/motif frequency; Primordia: primitive counts/
  bank size/promotion counts); CI scripts in the Linux lane.

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

## Standing Rules During Execution

- The integrity suite is a permanent CI gate; every new engine adds its
  resume-equivalence, read-only-export, and (where applicable) speciation
  hooks before its evidence counts.
- `evidence validate --require-artifacts` green before any registry
  citation merges (from Phase 3).
- Engine-only cohorts for parity/portfolio decisions; contender-including
  cohorts for external claims; enforced in validators, never by memory.
- The cumulative-gates rule (Definitions) applies to every exit.
- Mixed results are classified `inconclusive/mixed` and kept.
- Sub-WP expansion follows WP numbering unless a recorded dependency note
  says otherwise; expansions live in the consolidated plan or PR
  checklists only (never separate plan files).
- Lane rules (Parallel Execution Model) apply to every phase: ownership
  boundaries, interface freeze, cross-review by the other lane, and the
  joint integration WP before any exit-gate evaluation.

## Immediate Next Actions

1. Create the authoritative repository remote.
2. Update provenance and close B0.2 only after every pinned authority URL
   matches that configured remote.
3. Run both hosted workflows, collect their uploaded artifacts, and close B0.5
   only after the Linux and macOS evidence validates.
4. Rerun joint Gate B0 integration and keep the gate open on any failed item.
5. After all six items close, freeze the Phase 0 interfaces and split Lane A/Lane B
   exactly as defined in the Phase 0 lane block.
