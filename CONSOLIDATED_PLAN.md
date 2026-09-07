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

**Updated:** 2026-09-07. Revision 2 remains the governing plan baseline; this
consolidation updates execution status without changing specifications or gates.

This is the sole execution plan. Expand work packages here or in a PR-local
checklist. [README.md](README.md) owns capabilities and operating instructions;
[PROJECT_HISTORY.md](PROJECT_HISTORY.md) owns completed work, decisions and
verification references. Pinned [Lab specifications](claude-spec/README.md)
win on disagreement. The [program charter](PROGRAM_CHARTER.md) separates Lab,
Product and interop; Product implementation is outside this repository's plan.

## Immediate Next Actions

The technical baseline is `646dde2270d540877c7d9165718eb01a5b05b84c`.
The reviewed #10–#20 series is integrated, #21 supplies GPL-3.0-only licensing,
and #22 configures CodeRabbit. #9 was closed without catalog admission.
Both main CI lanes passed. Gate B0 is closed; Phase 0 remains open.

| Order | Deliverable | Completion condition |
| --- | --- | --- |
| 1 | WP-0.1b bounded catalog/freeze amendment | Explicit compatible-addition rules, preserved historical verdicts, reviewed replacement validator and trust-anchor transition. |
| 2 | WP-0.8 canonical catalog and packs | Eight `tier1_core` benchmarks and the required smoke/Tier-A packs resolve reproducibly with immutable IDs and complete metadata. Load validation is not decision-grade admission. |
| 3 | WP-0.10a reference integration and Phase 0 acceptance | Catalog-backed reference fixtures, regular export-contract coverage and an evidence matrix for every parent WP; both hosted lanes pass. |
| 4 | Phase 1 Contenders + Compare | Begin with one benchmark through fit/evaluate/export/ingest/report, then complete the full Phase 1 scope and exit. |

Supporting follow-ups belong to WP-0.1a: profile the B0 policy bottleneck before
optimizing it; verify CodeRabbit's effective file selection on a real follow-up
PR; decide a useful docstring policy for tests. The observed skipped-review
notice is an investigation item, not a verified global review outage. None of
these items substitutes for catalog or integrity acceptance.

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
evidence. The protected freeze PR and separate authorization attestation are
merged; freeze v2 is `merged_verified`. History retains the exact B0 bindings,
review records and probe paths. This state does not imply Phase 0 acceptance.

## Phase 0 — Workspace, Contracts, Integrity Foundation

**Objective:** validated contracts, benchmark resolution and a permanent
integrity gate proven against executable skeletons. Spec: claude-spec/01–04,
/13, /18. All ten parent checkboxes below represent acceptance, not whether
implementation exists. The current freeze validator requires them to remain
open; formal closure must include the appropriate reviewed gate transition.

### Current acceptance matrix

| Parent | Implemented and verified | Remaining acceptance work |
| --- | --- | --- |
| WP-0.1 | Workspace, package scripts, full cross-host foundation coverage, consolidated CI triggers | Final evidence mapping; bounded CI/review follow-ups below. |
| WP-0.2–0.5 | Strict export/budget/telemetry models, identities and RNG contracts | Map existing tests to every requirement; integrate regular export fixtures with the reference proof. |
| WP-0.6–0.7 | Atomic checkpoints, transactional store/workspace, verified reader and diagnostic consistency | Include persistence and failure results in joint acceptance. |
| WP-0.8 | Strict catalog and pack loaders | Production registry is empty; admit the specified benchmark definitions and packs after amendment. |
| WP-0.9 | LM-cache existence/size/checksum validators | Record contract acceptance; real LM execution belongs to later phases. |
| WP-0.10 | Real synthetic kill/resume proof, budget and protected-label tests, cross-host JSON evidence | Complete catalog/export integration and joint reference acceptance. Engine-specific hooks remain separately open. |

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
Remaining: profile B0 policy tests and measure any bounded change against the
same cases. Final main's macOS B0 step took 18m46s; foundation took 35s. These
are observations from one run, not a stable benchmark. Investigate effective
CodeRabbit path selection and the optional docstring warning separately.

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
WP-0.7 acceptance remains part of the phase evidence matrix. `_run_io` already
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
Freeze v2 remains effective until the replacement is accepted. Closed PR #9
admitted nothing; a successor must carry the complete amendment. Extraction of
remaining private export/catalog parser helpers stays conditional on amendment
and demonstrated value; keep seven package boundaries and avoid a framework.

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
**Evidence:** existing eight-case synthetic reports plus the missing
catalog/export integration evidence and requirement-to-test acceptance matrix.
**Failure conditions:** synthetic fixtures are called production/scientific
proof, placeholder hooks count as passing, or any parent is unaccepted.

The synthetic runner and probe are implemented, reviewed, merged and hosted.
They charge each candidate under an explicit policy, distinguish fresh and
inherited work, and recover a durable row ahead of its checkpoint without
reevaluation. Four kill boundaries cover failed and invalid attempts. Resume
rejects changed seed/config/label identities; diagnostics validate the complete
persisted state. These diagnostics are not the regular three-file export.
Remaining work integrates the accepted catalog and export contracts, names any
necessary schema decision explicitly, and closes the reference gate with the
full parent matrix. It does not invent an engine identity or claim general
exactly-once behavior before row commit. Engine resume hooks activate as engines
land; speciation behavior activates with Topograph, not a placeholder.

### Parent scope and phase exit

**Lane split & sync:** A owns WP-0.2–0.5; B owns WP-0.1 and WP-0.6–0.9;
WP-0.10 and the Phase 0 exit remain joint. Frozen interfaces are canonical
encoding/digests, export models and catalog-loader signatures. Freeze v2 and
its authorization are already merged and verified. This consolidation changes
no freeze bytes, source pins or acceptance state.

<!-- phase0-interface-freeze:begin -->
```yaml
freeze_id: phase0-interface-freeze-v2
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: 25352a4bd7c33b73077d9f9be231b2bb1b48109f
approved_tree: 78a72f1a2229d9e94cd78512be0585f08b2a5895
digests:
  canonical_digest_rng: 1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc
  export_models: f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72
  catalog_loaders: 3b804f54e14749e3f0ae1bcb06b0b8415f5954a312c3eaf9057001ea4832f2cc
reviews:
  - reviews/2026-07-23-phase0-lane-a-producer-a2-review.md
  - reviews/2026-07-23-phase0-lane-b-consumer-a2-review.md
status: merged_verified
lane_authorization: true
canonical_merge_commit: 5a98d9d45c4f2a7bc35bc75f93141473d0769e94
verified_at: 2026-07-23T07:27:10Z
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```
<!-- phase0-interface-freeze:end -->

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
