# EvoNN Lab (claude-spec) — Master Execution Plan

> **For agentic workers:** This is the master plan for building the Lab.
> Each work package (WP) expands into a bite-sized TDD sub-plan
> (`docs/plans/YYYY-MM-DD-wp-<id>.md` in the Lab repo) at execution time,
> executed via superpowers:subagent-driven-development or
> superpowers:executing-plans. Do not implement from this file alone —
> expand the WP first. Checkboxes track WP completion.

**Goal:** Build the claude-spec research platform — four distinct search
engines, a trust substrate, and an evidence loop — to the point where Gate
L-SCI (scientific conclusion) and Gate I1 (interop producer conformance)
are both reachable.

**Architecture:** uv workspace monorepo; engines as independent packages
exchanging file artifacts; Compare as orchestrator/auditor; per-run DuckDB;
MLX truth path with NumPy fallback. Normative source: `claude-spec/`
chapters 00–19. Where this plan and the spec disagree, the spec wins.

**Tech Stack:** Python ≥ 3.13, uv workspace, Pydantic 2 (strict at
boundaries), MLX (macOS truth path), NumPy (portable fallback), DuckDB
(per-run), Typer, pytest + ruff, scikit-learn (contender floor).

**Repository:** New repo (suggested: `~/Projekte/EvoNN-Lab`). At bootstrap,
this file becomes that repo's `CONSOLIDATED_PLAN.md` (single-active-plan
policy, claude-spec/18). Field lists and schemas are deliberately
referenced to spec chapters rather than duplicated — the spec is the source
of truth; sub-plans copy exact fields at expansion time.

## Global Constraints

- Python ≥ 3.13; one uv workspace lock at repo root (claude-spec/01).
- Engines MUST NOT import each other; Compare invokes engine CLIs and reads
  exports only (claude-spec/01 dependency rules).
- `evonn_shared` stays dependency-light: no search logic, no genomes, no
  engine runtime (claude-spec/01).
- Canonical benchmark IDs only at every export boundary (claude-spec/02).
- Budget accounting fields on every compare-visible export
  (claude-spec/03): `evaluation_count`, `actual_evaluations`,
  `cached_evaluations`, `failed_evaluations`, `invalid_evaluations`,
  `resumed_from_run_id`, `partial_run`, `evaluation_semantics`.
- One DuckDB writer per file, per-run DBs only (claude-spec/01).
- Every run directory: `config.yaml`, `metrics.duckdb`, `state.json`,
  `summary.json`, `report.md`, `checkpoints/` (claude-spec/01).
- Output-quality ladder L0–L4 (claude-spec/04); all engines reach L3 on
  Tier A and `tier1_core@64` before trusted claims.
- Branch/PR policy: never on `main`; `agent/<issue>-<slug>`;
  engine-advancement PRs carry the decision-gate bundle (claude-spec/18).
- **Foundation Integrity Gate** (charter + claude-spec/17 Phase 0 exit)
  precedes any trusted-evidence claim — see WP-0.10.
- New feature flags default off-or-better-default with prior behavior
  restorable (claude-spec/18).

## Phase Map And Dependencies

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
(contracts) (floor+     (Prism,     (evidence   (Strato,    (transfer   (QD, tiers, (perf, Obs,
 +integrity  Compare)    Topograph)  +stats)     Primordia)  proof)      L-SCI)      automation)
                                        │
                                        └──► Interop Producer Workstream (WP-I.*, parallel from Phase 3; Gate I0/I1)
```

---

## Phase 0 — Workspace, Contracts, Integrity Foundation

**Objective:** A bootable workspace where every later package can import
validated contracts, resolve benchmarks, and pass the integrity gate.
Spec: claude-spec/01, /02, /03, /04, /13, /18.

**Package layout created in this phase:**

```
EvoNN-Lab/
├── pyproject.toml                  # [tool.uv.workspace] members
├── EvoNN-Shared/
│   ├── pyproject.toml
│   ├── src/evonn_shared/
│   │   ├── contracts.py            # export contract models
│   │   ├── budget.py               # budget declaration + accounting models
│   │   ├── telemetry.py            # telemetry envelope + seeding metadata
│   │   ├── identity.py             # run IDs, content digests
│   │   ├── rng.py                  # named RNG stream derivation
│   │   ├── checkpoint.py           # atomic checksummed checkpoint publication
│   │   ├── storage.py              # RunStore: per-run DuckDB schema
│   │   ├── benchmarks.py           # catalog/pack resolution helpers
│   │   ├── lm_cache.py             # LM cache validation
│   │   └── training.py             # regression target scaling + affine calibration
│   └── tests/
├── shared-benchmarks/
│   ├── catalog/*.yaml              # Tier A + tier1_core benchmark specs
│   ├── suites/parity/*.yaml        # tier1_core, tier1_core_smoke, tier_a_contract
│   └── registry/canonical_ids.yaml # append-only canonical ID registry
├── scripts/ci/shared-checks.sh
└── .github/workflows/              # linux-trust-lane.yml, macos-engines.yml
```

- [ ] **WP-0.1 Workspace bootstrap.** Root `pyproject.toml` with uv
  workspace; ruff config; pytest config; `scripts/ci/shared-checks.sh`
  (ruff + pytest for EvoNN-Shared); Linux CI workflow running it; macOS
  workflow stub.
  *Verify:* `uv sync --all-packages --extra dev` clean;
  `bash scripts/ci/shared-checks.sh all` green on an empty test.
- [ ] **WP-0.2 Export contract models** (`contracts.py`). Pydantic-strict
  `Manifest`, `ResultRecord`, `RunSummary` with the exact field sets of
  claude-spec/04 (system, run/pack/seed identity, runtime block, seeding
  block, artifact listing; per-benchmark records with canonical ID, metric
  name/direction/value, status ∈ ok|failed|skipped|unsupported, params,
  seconds, bytes). Round-trip JSON writers.
  *Interfaces produced:* `Manifest.model_validate_json`,
  `write_manifest(path, Manifest) -> digest`.
- [ ] **WP-0.3 Budget models** (`budget.py`). `BudgetDeclaration` (the 7
  contract fields of claude-spec/03) + `BudgetAccounting` (the 8 accounting
  fields). Validators: `actual ≤ declared` unless `partial_run` semantics;
  `evaluation_semantics` non-empty for compare-visible exports.
- [ ] **WP-0.4 Telemetry + seeding models** (`telemetry.py`). Telemetry
  envelope floor of claude-spec/04; the 9 seeding fields of claude-spec/03
  with `unknown`-explicit semantics; ladder enum none|direct|staged.
- [ ] **WP-0.5 Identity + RNG streams** (`identity.py`, `rng.py`).
  Content-addressed digests (canonical serialization, digest-field-omitted
  rule); run ID scheme. `derive_stream(root_seed, name) -> np.Generator`
  for named streams (search, data, split, init, order, augmentation,
  mutation, benchmark_sampling, worker, stats) — deterministic and
  independent of process scheduling.
  *Interfaces produced:* `content_digest(obj) -> str`,
  `derive_stream(seed:int, name:str) -> Generator`.
- [ ] **WP-0.6 Atomic checkpoints** (`checkpoint.py`). Stage to temp path →
  fsync → checksum → atomic rename → manifest update referencing previous
  checkpoint digest. Crash between steps leaves the previous checkpoint
  authoritative.
  *Interfaces produced:* `publish_checkpoint(dir, payload) -> CheckpointRef`,
  `latest_valid_checkpoint(dir) -> CheckpointRef|None`.
- [ ] **WP-0.7 RunStore** (`storage.py`). Per-run DuckDB schema: `runs`,
  `evaluations` (immutable canonical rows), `artifacts`, `metadata`.
  Single-writer guard (lock file + PID); evaluations are append-only.
- [ ] **WP-0.8 Benchmark catalog + packs.** YAML schema per claude-spec/02
  (explicit metric direction, ceiling semantics, required contenders,
  runtime class); loaders in `benchmarks.py`; seed the catalog with the 8
  `tier1_core` benchmarks (iris_classification, wine_classification,
  breast_cancer_classification, moons_classification,
  digits_classification, diabetes_regression, friedman1_regression,
  credit_g_classification) + smoke variants; packs `tier1_core`,
  `tier1_core_smoke`, `tier_a_contract`; append-only canonical ID registry.
- [ ] **WP-0.9 LM cache validation** (`lm_cache.py`). Existence/size/
  checksum validation for byte-level LM caches; used from Phase 4 onward.
- [ ] **WP-0.10 Foundation Integrity Gate suite**
  (`EvoNN-Shared/tests/test_integrity_gate.py` + per-package hooks later).
  Named tests, all must pass before any trusted-evidence claim anywhere:
  `test_rng_streams_deterministic_and_independent`,
  `test_resume_equals_uninterrupted` (harness contract, exercised per
  engine from Phase 2), `test_checkpoint_publication_atomic_and_checksummed`,
  `test_evaluation_rows_immutable`, `test_export_is_read_only`
  (export never mutates run state), `test_measurement_vs_proxy_labeling`
  (byte/param fields carry `measured|estimated` provenance).
  *Exit criterion of the phase and standing gate for all later phases.*

**Phase 0 exit gate:** all WPs green; `shared-checks.sh` green on Linux CI;
Tier A packs audit-ready (loader validates ceilings/directions/floors);
integrity suite green.

---

## Phase 1 — Contenders + Compare Core

**Objective:** The trust layer works before any evolutionary engine exists.
Spec: claude-spec/05, /06.

**Packages created:** `EvoNN-Contenders/` (`evonn_contenders`),
`EvoNN-Compare/` (`evonn_compare`).

- [ ] **WP-1.1 Contender floor.** Required dependency-light pools per
  claude-spec/06: tabular (tree ensembles, MLP, logistic, SVM), synthetic
  subset. YAML pool config; runner producing per-benchmark results with
  `evaluation_semantics` = "one contender fit/eval pass per contender in
  the fixed pool"; export via `evonn_shared.contracts`.
  *CLI:* `evonn-contenders run --config <yaml>`,
  `evonn-contenders export --run-dir <dir> --pack <pack>`.
- [ ] **WP-1.2 Optional enhanced contenders.** `boosted` extra
  (xgboost/lightgbm/catboost) and `torch` extra (cnn_small,
  transformer_lm_tiny) behind extras; skips recorded in export
  (never silent).
- [ ] **WP-1.3 Compare pack resolution + case model.** Budget-stamped
  workspace-local compare packs; case = (pack, budget, seed); workspace
  layout per claude-spec/05.
- [ ] **WP-1.4 fair-matrix (contenders-only first).** Orchestrate runs,
  validate exports, budget parity checks, `lane_acceptance.json`,
  `fair_matrix_summary.md/.json` per case. Lane operating states
  contract-fair/trusted-core/trusted-extended + accounting/repeatability
  states.
  *CLI:* `evonn-compare fair-matrix --workspace <ws> [--preset|--pack]
  [--seeds] [--budgets] [--no-contenders] [--reset-workspace] [--open]`.
  Defaults: `local` = `tier1_core@64`.
- [ ] **WP-1.5 Trend artifacts.** Per-case `trend_rows.json`; append-only
  workspace `trends/fair_matrix_trend_rows.jsonl`; trend markdown with lane
  accounting + repeatability surfaced; `workspace-report` rebuild command.
- [ ] **WP-1.6 Static dashboard.** Single HTML + JSON payload: winner
  tables (full-system + projects-only recompute), lane health by budget,
  per-seed snapshots, multi-seed spread/CIs, Evidence Explorer stub,
  runtime table. Ceiling ties counted as ties, listed separately.
- [ ] **WP-1.7 benchmark-audit.** Pack admission audit per claude-spec/02:
  floors present, ceilings/directions explicit, cache validation, status
  passed/exploratory/blockers.
- [ ] **WP-1.8 output-quality.** L0–L3 classifier over run directories with
  per-run gap report (L4 arrives in Phase 3).

**Phase 1 exit gate:** contenders-only fair-matrix at `tier1_core@64`
produces `contract-fair` artifacts end-to-end; dashboard renders;
benchmark-audit green for `tier_a_contract` and `tier1_core`;
`compare-checks.sh` + `contenders-checks.sh` in Linux CI.

---

## Phase 2 — Prism + Topograph

**Objective:** The reference engine and first challenger at L3 on trusted
lanes. Spec: claude-spec/07, /08.

- [ ] **WP-2.1 Prism genome + families.** Frozen `ModelGenome` (full field
  list of claude-spec/07), content-addressed `genome_id`; family registry
  (FlexMLP, SparseMLP, MoEMLP, ImageConvNet, LiteImageConvNet,
  SequenceConvNet, LiteSequenceConvNet, SequenceGRUNet, TextEmbeddingModel,
  AttentionEncoderNet, SparseAttentionNet); compatibility matrix; compiler.
- [ ] **WP-2.2 Prism training runtime.** AdamW, cosine/constant LR with
  warmup, gradient clipping, early stopping, wall-time caps, NaN detection,
  multi-fidelity schedule, weight-inheritance cache (parent → family
  fallback → checkpoint; cross-family groups), regression
  scaling/calibration from `evonn_shared.training`.
- [ ] **WP-2.3 Prism pipeline.** Seeding with family diversity;
  undercovered-benchmark selection; archives (per-benchmark elites, Pareto
  quality-vs-params, family niches); reproduction (tournament, splice +
  uniform crossover with adaptive rate, domain-aware single-step mutation
  incl. morph ops); `state.json` resume; per-generation persistence.
  *Integrity hook:* `test_resume_equals_uninterrupted` implemented for
  Prism (2 generations, tiny config, compare event/candidate sequences).
- [ ] **WP-2.4 Prism run boundary + CLI.** Run directory contract; verbs
  `evolve/inspect/report/benchmarks/warm-cache/symbiosis export`; tiny
  smoke config + e2e CLI test.
- [ ] **WP-2.5 Topograph genome.** LayerGene/ConnectionGene (+ optional
  ConvLayerGene, expert genes, GateConfig) with innovation numbers;
  operator vocabulary (dense, sparse_dense, residual, attention_lite,
  spatial, transformer_lite); per-layer precision fields.
- [ ] **WP-2.6 Topograph precision modules.** `BitLinear` (ternary, STE,
  latent FP weights), `QuantizedLinear` (INT4/8 fake-quant); projections
  inherit target-layer precision; byte accounting with
  measured-vs-estimated labeling.
- [ ] **WP-2.7 Topograph compiler + training.** Graph-driven
  `EvolvedModel`; LayerNorm; Kaiming init; AdamW + cosine warmup + clip;
  Lamarckian `WeightCache` (structural hash; exact/partial/none modes,
  epoch ratios 0.3/0.6; savings visible in budget accounting).
- [ ] **WP-2.8 Topograph evolution loop.** Speciation by compatibility
  distance (materially affecting reproduction — integrity bar); phase
  scheduler explore/refine/polish with EMA operator scaling; novelty
  archive; MAP-Elites grid; per-benchmark elites; benchmark pooling;
  memory-aware process-pool evaluator; resume + scheduler-state
  checkpointing (atomic via `evonn_shared.checkpoint`).
- [ ] **WP-2.9 Topograph run boundary + CLI.** Same verb set as Prism;
  tiny smoke e2e; resume-equivalence test.
- [ ] **WP-2.10 Compare integration.** Both engines in fair-matrix; L3
  fields propagated to trend rows; macOS CI (`prism-checks.sh`,
  `topograph-checks.sh`); NumPy-fallback smoke path for both engines'
  export surface (Linux CI participation).

**Phase 2 exit gate:** 3-seed `trusted-core` cohort at `tier1_core@64`
(Prism + Topograph + Contenders), all systems L3, zero silent budget
undercounting, integrity suite green for both engines.

---

## Phase 3 — Evidence Registry + Statistical Layer

**Objective:** Durable research memory and decision-grade statistics.
Spec: claude-spec/12, /05 (decision gate).

- [ ] **WP-3.1 Evidence registry.** `evidence promote/validate`:
  `index.jsonl` rows (full field set of claude-spec/12 incl. git commit,
  backend class, host fingerprint, checksums, decision status);
  immutability + supersession; `--copy-artifacts` compact summaries.
- [ ] **WP-3.2 Evidence report + decision labels.** Grouping by
  label/pack/budget; minimum-seed gates (A:3, B:3/2, C:3/2, D:3);
  conservative labels (`gain`, `no_material_change`, `inconclusive`,
  `blocked`); "not enough evidence" first-class.
- [ ] **WP-3.3 Statistical summaries.** Rank distributions, per-benchmark
  score distributions, budget slopes, floor-margin distributions,
  ceiling-tie exclusion, effect size vs best required contender, bootstrap
  CIs; synthetic fixtures for ceiling ties, missing runs, backend drift,
  mixed budgets.
- [ ] **WP-3.4 Registry-backed dashboard history.** Last-N full-run
  overview from registry rows; L4 classifier added to output-quality.
- [ ] **WP-3.5 Decision gate operationalization.** PR template with the
  evidence bundle; policy test preventing competing root plan files;
  `historical-baseline` import command.

**Phase 3 exit gate:** a before/after engine change is judged end-to-end
from registry-backed evidence with a statistical decision label.

---

## Phase 4 — Stratograph + Primordia

**Objective:** Complete the four-engine portfolio at L3; Tier B online.
Spec: claude-spec/09, /10, /02.

- [ ] **WP-4.1 Stratograph genome + codec.** HierarchicalGenome (macro
  nodes/edges + cell library; CellNodeGene/CellEdgeGene); all invariants of
  claude-spec/09; structural metrics (macro depth, cell depth, reuse
  ratio); content digesting.
- [ ] **WP-4.2 Stratograph compiler + proxy evaluator.** CompiledHierarchy/
  CompiledCell with cell reuse; trained heads (GELU classifier warm-start,
  LM vocab projection); fidelity-regime labels per claude-spec/03.
- [ ] **WP-4.3 Stratograph search ops.** Width/activation changes, clone,
  specialize, add-macro-node, macro rewiring, skip edges, motif rewrite;
  crossover preserving parent macro edges; task/dimension-aware seed
  profiles (LM, regression, high-dim tabular) — crossover-first diversity,
  no broad exploitation slot (known-negative).
- [ ] **WP-4.4 Stratograph ablation harness + motif mining.**
  `ablate`/`ablate-matrix` over flat/unshared/shared/no-clone/
  no-motif-bias; `motifs analyze` for repeated winning sub-cells.
- [ ] **WP-4.5 Primordia engine.** Primitive genome + MLX lane + NumPy
  fallback; runtime caps (epoch caps, expensive-family caps, architecture
  clamps per family); bounded elite/archive search; budget-matched
  per-benchmark scheduling.
- [ ] **WP-4.6 Primordia artifacts.** Primitive bank summary,
  `seed_candidates.json`, `search_leaders.json`; `seed export` CLI;
  inspect/report surfaces.
- [ ] **WP-4.7 Tier B benchmarks + packs.** Extend catalog (OpenML set,
  small image, LM caches via WP-0.9); `tier_b_core`, `tier_b_core_v2`
  additive + cumulative; presets; audits.
- [ ] **WP-4.8 Five-system integration.** Both engines in fair-matrix at
  L3; resume-equivalence + integrity hooks; CI scripts
  (`stratograph-checks.sh`, `primordia-checks.sh`) in the Linux lane.

**Phase 4 exit gate:** five-system Tier B `trusted-extended` cohort at
3 seeds; all four engines L3; ablation harness produces its first
shared-vs-flat evidence.

---

## Phase 5 — Native Transfer Proof

**Objective:** Prove, refute, or classify the cumulative-search claim.
Spec: claude-spec/11.

- [ ] **WP-5.1 Seed artifact schema hardening** in `evonn_shared` (full
  contract of claude-spec/11 incl. contamination policy, compatible
  targets, checksum); artifact gating validator.
- [ ] **WP-5.2 Topograph native seed consumption.** `unseeded`/`seeded`/
  `staged_seeded` modes that demonstrably change initialization/search
  bias (assertable in tests); accounting modes free/reported/charged
  (default `reported_prior`).
- [ ] **WP-5.3 Compare transfer surfaces.** `seeded-compare` (canonical
  control lane) and `transfer-regimes` (none/direct/staged, regime-vs-
  control verdicts, per-seed + aggregate reports); portable-vs-native
  proof state recorded in registry rows.
- [ ] **WP-5.4 Proof campaign.** `tier_b_core_v2@96` × 3 seeds →
  `@384` × 2 seeds if signal → Tier C exploratory; classify
  gain/regression/no_gain/inconclusive; promote evidence; failure
  attribution (seed quality vs ingestion vs benchmark mismatch vs
  accounting).

**Phase 5 exit gate:** one auditable native transfer outcome in the
registry with repeated evidence and explicit classification.

---

## Phase 6 — QD, Portfolio Decisions, Tier Hardening, L-SCI

**Objective:** Evidence-backed engine roles and the Lab's scientific
conclusion. Spec: claude-spec/14, /12, /02.

- [ ] **WP-6.1 Descriptor schema** (shared, optional) + Topograph
  descriptor exports + Compare archive report (occupancy, fill ratio).
- [ ] **WP-6.2 One QD experiment branch** (Topograph or Primordia) vs
  baseline at equal budget; promote only if diversity improves without
  destroying quality.
- [ ] **WP-6.3 Stratograph LM-flatline diagnostic** (evaluator vs genotype
  vs compiler vs policy attribution) + hierarchy ablation evidence.
- [ ] **WP-6.4 Tier C/D hardening.** Tier C packs + promotion gates (two
  clean 512, one clean 1024); Tier D admitted broad lane; Tier E candidate
  audit file (admission reports only); runtime-envelope-first proof
  scaling (1 seed × 1 budget within wall-clock envelope before the full
  matrix).
- [ ] **WP-6.5 Portfolio status assignment.** Every engine gets an
  evidence-backed status (reference/challenger/specialist/seed_source/
  baseline_only/archive_candidate) with registry links; statuses in
  dashboard/docs.
- [ ] **WP-6.6 Gate L-SCI evaluation.** Qualify the contender floor
  (adequacy labels non-weak on the claim surface); either promote a
  repeated-evidence engine win/tie on a meaningful non-smoke subset, or
  promote the evidence-backed negative conclusion with recorded portfolio
  consequences. Either outcome passes the gate; silence does not.

**Phase 6 exit gate:** L-SCI answered and recorded; engine roles
evidence-backed; Tier C promoted or explicitly exploratory with blockers.

---

## Phase 7 — Performance Frontier, Observatory, Automation

**Objective:** Sustainable operation. Spec: claude-spec/13, /15, /17.

- [ ] **WP-7.1 performance-baseline workflow.** Measurement bundles
  (medians, evals/sec, quality/sec, cache reuse, exclusion reasons);
  optimization branch template: baseline → one change → identical
  remeasure → accept/scrap/inconclusive.
- [ ] **WP-7.2 First optimization slices.** One per branch from the
  candidate list (MLX batching, fallback vectorization, early rejection,
  dedup with cache accounting) — each with before/after artifacts.
- [ ] **WP-7.3 Observatory.** FastAPI + Jinja2 + Chart.js read-only app
  per claude-spec/15 (scanner, API, pages, mandatory plain-language info
  banners); reads workspaces + registry.
- [ ] **WP-7.4 Scheduled automation loop.** Tiny-budget trend-detection
  configs; recurring job that pulls latest, runs bounded smoke + tiny
  compare, appends to the trend surface; results accumulate instead of
  staying anecdotal.

**Phase 7 exit gate:** one full optimization accept/scrap cycle completed;
Observatory browsable; automation loop has ≥ 2 weeks of accumulated trend
rows.

---

## Interop Producer Workstream (parallel, from Phase 3)

**Objective:** Gates I0 (Lab side) and I1. Spec: claude-spec/19,
PROGRAM_CHARTER.md Workstream C.

- [ ] **WP-I.1 Contract versioning.** Semantic versions + changelogs for
  export contract, seed artifact schema, canonical ID registry.
- [ ] **WP-I.2 Mechanism-dossier schema + validator + worked examples**
  (including one negative-result dossier). This is new implementation
  work, not a documentation task.
- [ ] **WP-I.3 Golden producer fixtures.** Valid, invalid, corrupt, and
  old-version examples of every export surface, published for the
  Product's reference-consumer qualification.
- [ ] **WP-I.4 Producer conformance suite.** Lab-side validation that
  every published artifact class passes its own schema + digest +
  provenance checks (Gate I1 evidence).
- [ ] **WP-I.5 Reverse-dossier ingestion.** Backlog intake path for
  Product feedback (`product-feedback` origin marker), incl. triage rule
  for failed-adoption reports.

---

## Standing Rules During Execution

- The integrity suite (WP-0.10) is a permanent CI gate; any phase adding a
  new engine adds its resume-equivalence and read-only-export hooks.
- Every engine-quality change from Phase 2 onward carries before/after
  evidence per the decision gate; mixed results are classified
  `inconclusive/mixed` and kept, not argued into wins.
- Engine-only cohorts for parity decisions; contender-including cohorts
  for floor claims; never conflated.
- Sub-plan expansion order within a phase follows WP numbering unless a
  recorded dependency note says otherwise.

## Immediate Next Actions

1. Create the Lab repository; copy `claude-spec/` in (or submodule the
   spec repo); install this file as `CONSOLIDATED_PLAN.md`.
2. Expand **WP-0.1** into the first bite-sized TDD sub-plan and execute.
3. Proceed through Phase 0 WPs in order; hold the Foundation Integrity
   Gate review at phase exit before starting Phase 1.
