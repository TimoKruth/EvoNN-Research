# 16 — Legacy Tracks: Full Record And Resurrection Candidates

The current four-engine program descends from three earlier projects — EvoNN
(Track A), EvoNN-2 (Track B), and EvoNN-Symbiosis. They are deprecated as
codebases but not as idea space. This chapter specs them fully: what they
were, what they proved, which mechanisms already live on, and which are
explicit resurrection candidates.

---

## Track A — EvoNN (Family-Based Macro NAS)

**Thesis:** benchmark-rich family-space NAS on Apple Silicon. Direct ancestor
of Prism; most of its machinery is specified in ch. 07 already.

### Scale achieved

17 model families (the 16 base families plus `causal_transformer` with GQA
and searchable FFN ratio); 102 implemented benchmark definitions in 37 packs
across synthetic, classic, downloaded, MedMNIST, torchvision, OpenML(-CC18),
NAS-Bench-360, TALENT, HuggingFace, MLPerf Tiny, language-modeling, and
parity tiers; 4 modalities; 400+ tests; validated against 7 external
contenders (Ray Tune, NNI, AutoGluon, TabPFN, XGBoost, LightGBM, FLAML) on
equal budgets — and beat several of them.

### Key design decisions (proven; carried forward)

1. MLX-first, no PyTorch fallback for the engine itself.
2. Offline-first benchmarks; downloads require explicit `warm-cache`.
3. Quality-first archives; deployment metrics (quantization retention,
   latency, size) in separate archive views, optionally blended.
4. Content-addressed genomes (genome_id = content hash).
5. Seed-anchored normalization: quality normalized against the seed genome's
   baseline, making cross-benchmark aggregation meaningful.
6. `state.json` (full resumable state each generation) for resume; DuckDB
   for queryable metrics — resume never depends on the DB.

### Speed optimizations (proven set)

Multi-fidelity (35%/65%/100% epoch scaling); promotion screening (early
generations evaluate a benchmark subset, prune below threshold before full
fan-out); within-run evaluation cache keyed (genome_id, benchmark_id);
warm-start weight inheritance (~95% hit rate, parent → family fallback →
checkpoint, cross-family transfer between compatible groups); tensorized
dataset caching; automatic failure-skip for repeatedly failing
family×benchmark combos; validation-based early stopping.

### Mechanisms not yet fully carried into the new program

- **MOME multi-objective archive** and deployment-Pareto views → ch. 14
  resurrection candidate.
- **Deployment profiling (int8/int4 quantization retention)** after
  training → Topograph deployment evidence (ch. 14).
- **External contender harness** (Ray Tune/NNI/AutoGluon/TabPFN/XGB/LGBM/
  FLAML) → ch. 06 resurrection candidate.
- **Text generation from evolved checkpoints** (`generate` CLI) — small but
  useful qualitative surface for LM benchmarks.
- **Benchmark adapters** for NAS-Bench-360, TALENT, MedMNIST, HuggingFace,
  PhysioNet, Freesound/Zenodo — the "synthetic stub first, real data later"
  integration pattern is the template for Tier E admission work.
- **Cache status reporting** (`benchmarks cache-status`, CACHE_STATUS doc).

---

## Track B — EvoNN-2 (NEAT Topology Evolution)

**Thesis:** topology/speciation/QD NAS. Direct ancestor of Topograph
(ch. 08 absorbs most of it: innovation tracking, speciation, Lamarckian
inheritance, novelty + MAP-Elites, mixed precision, MoE genes). 510 tests
green at deprecation.

### Design docs worth preserving as specs

- **Training/Lamarckian/QD design (2026-04-02)** — the three-phase
  improvement program now embedded in ch. 08: (1) training foundation
  (cosine warmup, LayerNorm in the DAG, AdamW, grad clipping, Kaiming init),
  (2) Lamarckian weight cache with exact/partial/none inheritance modes and
  epoch scaling, (3) QD (behavior descriptors, novelty activation,
  MAP-Elites). Success criteria used: ≥10% Tier-1 fitness gain (P1), ≥40%
  compute reduction per generation (P2), ≥2× unique topologies (P3). Its
  backward-compatibility discipline — every new feature defaulting to
  off-or-better-default with the old behavior restorable — is the template
  for engine changes.
- **Mixed-precision NAS proposal (2026-03-16)** — per-layer
  weight-bits/activation-bits/sparsity genes; BitLinear (ternary, STE,
  latent FP weights); QuantizedLinear (INT4/8 QAT); precision inherited from
  target layer; hardware-aware fitness (memory budget, latency target);
  composition with NSGA-II, inheritance, self-adaptive mutation, speciation;
  honest note that MLX matmul gives no speedup without custom kernels.
  Absorbed into ch. 08; the NSGA-II multi-objective selection part remains
  open work under ch. 14.
- **Quantization-aware evolution proposal** — QAT during evolution rather
  than post-hoc; subsumed by the above.
- **MoE design (2026-03-18)** — expert genes + gating config as genome
  parts; lives on as Topograph's optional MoE head and Prism's `MoEMLP`
  (known flaky gradient test documented at deprecation — treat MoE gradient
  flow as a risk area with dedicated tests).
- **10x expansion design (2026-03-16)** — the numbered capability roadmap
  (1.1 self-adaptive mutation rates, 1.3 NSGA-II, 1.4 speciation, 1.5 weight
  inheritance, 2.4 convolutional genes) that sequenced Track B; useful as a
  dependency map for Topograph feature work.
- **Real-world benchmarks design / evaluation-pipeline speedup /
  multi-benchmark generalization** — dataset caching, pool evaluation, and
  generalization pressure designs whose surviving form is the shared
  benchmark catalog + benchmark pooling in ch. 08.

### Open items at deprecation (now Topograph/ch. 14 backlog)

Pareto-style size/quality selection for mixed precision; more high-budget
parity evidence; native Transformer/attention gene (Phase B5).

---

## EvoNN-Symbiosis (Comparison Layer, Transfer Gates, Hybrid)

**Thesis:** protocol-first comparison of the two parents under matched
budgets, staged S1–S4: contracts/validation/ingest → campaigns/statistics/
leaderboards → transfer experiments with go/no-go gates → narrow hybrid work.
Direct ancestor of Compare (ch. 05) and of the transfer protocol (ch. 11).

### Principles that became the platform

Protocol-level integration first; canonical benchmark IDs at the export
boundary; evaluation-count parity as the primary fairness axis; unsupported/
skipped/failed coverage always visible; comparison works from `manifest.json`
+ `results.json` alone; phase gates are real — hybrid claims require
measured transfer evidence.

### The S3 go/no-go gate (the platform's founding proof)

Exit criteria: ≥1 imported mechanism measured in isolation; ≥5% relative
improvement; effect survives both parent baselines under matched budgets;
clear attribution. Result (2026-04-04): **GO** — multi-fidelity + residual
mutations imported A→B improved `friedman1_regression` median MSE ~7.4 → ~2.6
(**65%**), with EvoNN's own performance unchanged (no seesaw), cleanly
attributed. Secondary: QD+exploration raised B's benchmark win rate 22.5% →
27.5% (partial pass — helps, insufficient alone). Also observed: B's genuine
topology-freedom win on `digits_image` (80–100% win rate) — an
architecture-class advantage, not an imported mechanism. Tier 3
(topology-leaning) confirmed B could win pairs at higher budget; Tier 2
(image-leaning) blocked on dataset caching, an infrastructure lesson.

### The Hybrid engine (S4) — resurrection candidate

Scope justified by the S3 evidence:

1. **Topology-evolved macro templates** — use Track B's DAG search to
   discover topology shapes, then fill nodes with Track A's family building
   blocks (conv2d for spatial, attention for tabular/text, residual MLPs for
   regression). This addresses topology search's weaknesses while keeping
   its freedom.
2. **Per-benchmark elite archive imported into the topology engine.**

Rules that made hybrid work honest: both parent baselines run as mandatory
controls; hybrid exports use the same contract (`system: hybrid`); per-run
DuckDB via its own run store; pre-fix artifacts explicitly labeled prototype
evidence.

**In the current program**, "hybrid" is the far-horizon merged system
(ch. 17): keep Prism/Topograph/Stratograph as references, merge only proven
advantages — family priors and coarse selection from Prism; flat routing and
topology search from Topograph; motif reuse/specialization/hierarchy from
Stratograph; primitive priors from Primordia. The macro-template idea is the
most concrete candidate design for that system.

### Other Symbiosis assets absorbed or retained

Campaign orchestration with generated `campaign.yaml` manifests and
`campaign_summary.md` as canonical evidence (→ Compare `campaign`);
multi-seed leaderboards with Wilcoxon/bootstrap statistics (→ ch. 12);
tiered parity packs incl. honest "leaning" labels (→ ch. 02 symmetry field);
the Observatory web frontend (→ ch. 15); workspace audits and transfer
analyses as report patterns.

---

## Cross-Cutting Lessons Fed Into This Spec

1. **Canonical IDs or chaos** — parents used different native IDs; mapping
   at the export boundary saved the program (ch. 02).
2. **Transfer must be gated and attributed** — the S3 protocol is now the
   ch. 11 template.
3. **Infrastructure blocks science** — Tier 2 stalled on dataset caching;
   hence warm-cache verbs, cache validation, and cache-status surfaces.
4. **Fairness bugs invalidate evidence quietly** — corrected-b1008 reruns
   taught that pre-fix artifacts must be labeled prototype, and that budget
   accounting belongs in the contract (ch. 03).
5. **Architecture-class wins are real but narrow** — digits_image showed a
   topology engine can genuinely beat family search somewhere; the ladder
   exists to find *where*, honestly.
6. **Deliberate duplication beats hidden coupling** — the Primordia
   independence decision (ch. 01).
7. **Autonomy patterns work** — keep-or-revert fixed-budget loops
   (autoresearch) produce real hardware-local findings (ch. 15).
