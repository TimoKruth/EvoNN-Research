# 02 — Shared Benchmarks And The Ladder

`shared-benchmarks/` is the benchmark source of truth for the whole umbrella.
Without shared benchmark identities and pack semantics, EvoNN collapses into
parallel repos talking past each other.

## Canonical Benchmark Identity

Every benchmark has exactly one **canonical ID** used at every export and
comparison boundary. Engines MAY use native IDs internally, but their
symbiosis export MUST map to canonical IDs via an explicit, tested
`CANONICAL_BENCHMARK_IDS` mapping.

Historical examples of why this matters (from the parent tracks):
`iris` (EvoNN-2 native) → `iris_classification` (canonical);
`friedman_regression` (EvoNN native) → `friedman1_regression` (canonical).

Rules:

- Canonical IDs are lowercase snake case and self-describing, usually
  `<dataset>_<taskkind>` (e.g. `credit_g_classification`,
  `diabetes_regression`, `tinystories_lm`).
- A canonical ID never changes meaning. Changing data, split policy, or
  metric requires a **new** ID.
- Resolution rule: if a package has a local fallback definition and
  `shared-benchmarks/` disagrees, `shared-benchmarks/` wins.
- `EVONN_SHARED_BENCHMARKS_DIR` may override the folder location; engines
  also honor package-level override env vars (e.g. `PRISM_CATALOG_DIR`,
  `PRISM_PARITY_PACK_DIRS`, `PRISM_LM_CACHE_DIR`).

## Benchmark Spec Schema

Each benchmark is one YAML file under `catalog/`, validated as a Pydantic
model:

```yaml
id: my_benchmark                # canonical ID
display_name: My Benchmark
status: implemented             # planned | implemented | experimental | disabled
task_kind: classification      # classification | regression | language_modeling | forecasting
input_modality: tabular         # tabular | image | text | sequence
input_shape: [10]
output_dim: 3
primary_metric:
  name: accuracy
  direction: max                # max | min — metric direction is always explicit
ceiling:                        # explicit ceiling semantics (null when unbounded)
  value: 1.0
  tie_policy: not_evidence      # ceiling ties are never superiority evidence
budget_epochs: 20
runtime_class: fast             # estimated local runtime class
required_contenders: [logistic, tree_ensemble]   # minimum floor set (ch. 06)
tags: [offline]                 # offline | downloaded | generated | …
```

Requirements:

- **Metric direction MUST be explicit.** Compare must never guess.
- **Ceiling semantics MUST be explicit.** Accuracy/F1/AUC-style ceiling ties
  are excluded from superiority claims; metrics without a natural ceiling use
  best-observed comparison only.
- **Required contender floor** metadata is mandatory before a benchmark can
  enter any decision-grade pack.
- Generated or sliced data (LM caches, synthetic tasks) MUST have cache
  validation (checksums verified by `evonn_shared`).

## Task Domains Covered

The catalog spans, at minimum:

- **Tabular** — sklearn classics (iris, wine, breast_cancer, digits,
  diabetes), synthetic (moons, circles, blobs, xor, friedman1), OpenML
  (credit_g, wilt, gas_sensor, mfeat_factors, segment, qsar_biodeg, …)
- **Image** — small image classification (digits-as-image, MNIST-family,
  reduced CIFAR-style tasks where floors are honest)
- **Sequence / text** — sequence classification, lightweight text tasks
- **Language modeling** — a strict split between *smoke* LM fixtures
  (`tiny_lm_synthetic`) and *real cached* LM benchmarks (`tinystories_lm`,
  `wikitext2_lm` with validated byte-level caches). LM claims MUST state
  which surface they used.

## Packs And Suites

A **pack** (suite) is a named YAML list of benchmark IDs plus policy:

```yaml
pack_name: tier_b_core_v2
ladder_tier: B
benchmarks: [ ... canonical ids ... ]
budget_policy:
  evaluation_count: 96          # default budget when a pack is targeted directly
symmetry: symmetric             # symmetric | leaning-<system> (labeled honestly)
```

Pack families:

- **Parity packs** (`suites/parity/`) — the canonical shared comparison
  surfaces. `tier1_core` (8 symmetric benchmarks) is the trusted daily
  recurring lane. `tier1_core_smoke` is its smoke variant.
- **Ladder packs** — `tier_a_contract`, `tier_b_core`, `tier_b_core_v2`,
  `tier_c_architecture_sensitive`, `tier_d_broad_shared`, plus future
  `tier_e_*` candidates.
- **Additive increments and cumulative variants.** Ladder tiers are additive:
  Tier B's pack contains only benchmarks new at Tier B, so running higher
  tiers after lower tiers never reruns the same benchmark. Every tier also
  has a `_cumulative` variant (A+…+tier) for one-shot full comparisons.
  Reference sizes from the parent project: additive A=8, B(v2)=6, C=8, D=5;
  cumulative A=8, B=14, C=22, D=27.
- Budgets for cumulative packs MUST divide cleanly across the benchmark
  count (e.g. 22 Tier C cumulative benchmarks → budgets 154/264/374/484 in
  the 150–500 range).

## The Benchmark Ladder (Tiers A–E)

The ladder prevents two failures: overfitting to toy tasks while pretending
progress, and leaping to frontier tasks before the evaluation stack can
support honest claims. **Climb, don't leap.**

### Tier A — Smoke and sanity
Tiny, near-deterministic tasks. Purpose: prove pipelines work; catch
regressions; CI. Value: engineering trust, never scientific claims.
Reference budgets: 16, 64.

### Tier B — Core local research
Real datasets, laptop-bounded, diverse enough to expose benchmark-specific
overfitting. **The default proving ground for day-to-day work.**
`tier_b_core` is the canonical compact lane; `tier_b_core_v2` the expanded
additive lane. Reference budgets: 96/384/768/1536 (v2); 64/256/1000 (compact).

### Tier C — Architecture-sensitive stress
Harder generalization; visible quality-vs-compute/bytes/latency tradeoffs;
where search abstractions should separate from one another. Kept
**exploratory** until promotion requirements are met (two clean 512-budget
runs + one clean 1024 run). Reference budgets: 128/512/1024/2048 (additive),
132/528/1056/2112 (cumulative).

### Tier D — Broad system-like packs
Longer loops, more expensive scoring, program-like/code-like/retrieval-ish
tasks; hard-regression and real-LM sidecars. Used primarily as a
stress/regression detector; stays on a separate broad-lane leaderboard,
admitted-benchmark-only. Reference budgets: 200/400/800/1600.

### Tier E — Frontier and aspirational
North-star classes: reduced SWE-style tasks, code repair, long-horizon
reasoning, agent-like surfaces — any hard family a neural system might attack
in a budget-aware way, not only LLM-style tasks. Tier E starts as a
**candidate list with admission reports**, never as a large suite.

Tier E candidate areas: longer TinyStories slices; WikiText-2 medium windows;
byte- and token-level LM variants; sequence-copy/algorithmic tasks; licensed
code/text mini-corpora; MNIST/FashionMNIST full + corrupted variants;
CIFAR-like tasks with honest floors; larger OpenML tasks; high-cardinality
categorical and imbalanced classification (non-accuracy primary metrics);
noisy regression with robust metrics; controlled synthetic ladders isolating
nonlinearity, interaction order, noise, dimensionality, and imbalance.

## Admission Gates

A benchmark MAY enter candidate status for a tier when all of these hold:

- data reproducible locally; metric direction explicit; ceiling semantics
  explicit; required contender floor exists; runtime class estimated;
  every engine can produce L3 artifacts or explicitly declares
  `unsupported`; cache validation exists for generated/sliced data; budget
  divisibility defined for at least two budgets.

A benchmark becomes **decision-grade** only after:

- two clean repeated runs at low budget, one at mid budget;
- output-quality checks pass (ch. 04);
- the contender floor is not `weak_floor` (ch. 06);
- the dashboard displays it without special manual interpretation.

Every new pack MUST declare: ladder tier, modalities, expected local runtime
class, minimum contender set, suitability (smoke / daily / overnight /
special-study), and whether full-fidelity evaluation is local-safe or needs
staged reduction.

Audit tooling: `evonn-compare benchmark-audit --pack <pack>` MUST pass with
zero blockers before a pack is treated as decision-grade (ch. 05).

## LM Cache Handling

- `lm_cache/` holds prepared byte-level datasets for real LM benchmarks.
- `evonn_shared` provides cache validation (existence, size, checksum).
- Engines expose `warm-cache` / `list-lm-caches` CLI verbs.
- Smoke LM fixtures are for pipeline validation only; expanded-lane LM
  evidence MUST come from the validated real caches.

## What To Avoid

- treating Tier A wins as broad capability evidence
- using Tier E tasks as routine default evaluations
- adding packs without contender expectations
- mixing incomparable tasks without declaring why they belong together
- hiding evaluation reductions or shortcuts in reports
- introducing pack names that collide with the legacy numeric lane vocabulary
