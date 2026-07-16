# 08 — Topograph: Topology-First Search Engine

## Thesis

Topograph asks: **what flat DAG of learned operators should solve this task,
under real hardware and deployment constraints?** Topology is the primary
search object, not a side effect of family choice. It is the test bed for
graph evolution, operator-level search, quality-diversity archives, and
hardware-aware scoring — the direct descendant of the NEAT-style Track B
lineage, modernized.

Role in the portfolio: **primary challenger** and likely **first transfer
consumer** (`Primordia → Topograph`). Evidence bar: Topograph must win or tie
Prism on a meaningful topology-sensitive subset, or become a
specialist/transfer consumer rather than a primary challenger.

Long-run north star: a hardware-aware topology search platform — "find me a
model family for this task, under this latency / memory / precision budget,
on this target device" — producing a reusable **topology atlas**, not one
winner.

## Genome

A `Genome` of gene collections with NEAT-style innovation-number tracking:

- `LayerGene` — width; activation; **weight precision**; **activation
  precision**; sparsity; topological order; operator type; attention head
  count; enabled flag; innovation number.
- `ConnectionGene` — source/target references + innovation numbers (graph
  wiring; alignment basis for crossover and weight inheritance).
- optional `ConvLayerGene` — spatial operators.
- optional expert genes + `GateConfig` — mixture-of-experts routing.

Operator vocabulary (extensible): `dense`, `sparse_dense`, `residual`,
`attention_lite`, `spatial`, `transformer_lite`. Each node is a computation
style; precision and sparsity are part of the architecture itself.

### Mixed precision as genome property

Per-layer `weight_bits` ∈ {TERNARY(1.58-effective), INT4, INT8, FP16}, with
matching activation precision fields. Implementation modules:

- `BitLinear` — ternary {-1,0,+1} weights via absolute-mean scaling, INT8
  activation quantization via absolute-max scaling, straight-through
  estimator (`stop_gradient(quantized − latent) + latent`), full-precision
  latent weights updated by the optimizer (BitNet-b1.58 pattern on MLX).
- `QuantizedLinear` — INT4/INT8 fake-quantization (QAT) with per-tensor
  max-abs scaling and STE.
- Projections inherit `weight_bits` from their **target** layer.
- Honest claim: on MLX today this constrains representations and model
  bytes; inference speedups require future ternary kernels/Metal shaders —
  never claim latency wins the runtime doesn't deliver.

## Compilation

Genome → MLX `EvolvedModel`: sort layers by topological order; filter to
reachable regions; build per-connection projection modules; attach
operator-specific modules; optional LayerNorm per hidden layer; optional MoE
head; precompute routing tables. Forward pass is graph-driven: merge incoming
projections at each node, then apply node-specific operator logic.

## Evolution Loop

Per-generation typed pipeline state: generation number, population,
fitnesses, model byte estimates, behavior descriptors, benchmark results, raw
losses, current phase, total evaluations.

1. Seed initial topology population.
2. Evaluate on one benchmark or a sampled **benchmark pool** (optional
   percentile aggregation across the pool).
3. Score fitness, optionally blending novelty:
   `adjusted = (1−λ)·fitness + λ·novelty` (λ = `novelty_weight`, default off).
4. Update archives: novelty archive (k-NN in behavior space); MAP-Elites
   grid; per-benchmark elites.
5. Adapt mutation statistics from observed outcomes.
6. Reproduce (NEAT-style crossover aligned by innovation numbers; structural
   and parametric mutations, incl. residual/skip insertion).
7. Persist state, scheduler state, archives, innovation counters.

### Phase-based adaptive mutation scheduling

Three phases — `explore`, `refine`, `polish` — each with its own operator
probability profile; every operator's probability is additionally scaled by
an EMA of its observed success. Mutation policy is partly hand-shaped, partly
learned per run. Scheduler state checkpoints with the run.

### Speciation (ancestral capability, SHOULD be retained)

NEAT-style speciation by structural compatibility distance protects young
structural innovations within the population. Speciation, novelty pressure,
and MAP-Elites operate at different scales and complement each other:
intra-population protection / soft exploration pressure / hard per-niche
diversity guarantee.

## Quality-Diversity Machinery

Behavior descriptor (basis; extend per ch. 14):
`[dag_depth, max_width, skip_count, mean_weight_bits, connectivity_density]`.
MAP-Elites grid bins each dimension; each cell keeps its best genome; a
configurable fraction of parents is drawn from the archive
(`map_elites_selection_ratio`) to reinject diversity. Track archive fill
ratio, per-cell improvement counts, and graph-edit distance from seeds.

## Weight Inheritance (Lamarckian)

`WeightCache` keyed by structural hash (sorted layer + connection innovations
+ precision settings), bounded LRU (≈ 2× population), in-memory per run.
Inheritance modes: **exact** match → inherit all weights, train
`finetune_epoch_ratio` (default 0.3); **partial** (same topology, different
widths/precision) → inherit matching layers by innovation number, Kaiming-init
the rest, train `partial_epoch_ratio` (default 0.6); **none** → full init,
full epochs. Expected compute savings ≈ 50% per generation; savings MUST be
reflected in budget accounting (cached/inherited work visible).

## Parallelism And Caching

Explicitly separate serial cache-sensitive work from parallel expensive
training work, so weight inheritance and parallel execution coexist. The
process-pool evaluator estimates worker count conservatively from data size,
weight-snapshot size, CPU budget, and system memory. Evaluation memoization
is reused across the run with explicit cache accounting.

## Training Substrate

AdamW (decoupled weight decay), cosine warmup-decay LR schedule (10% warmup
ramp from lr/10, cosine to lr/100), gradient clipping (default max-norm 1.0),
LayerNorm in the DAG, Kaiming fan-in init for all projections, model-byte
accounting, regression target scaling/calibration from
`evonn_shared.training`.

## Hardware-Aware Objectives

Fitness must be able to include device reality: quality, latency, memory
footprint, parameter efficiency, precision regime, energy/throughput proxies,
compileability. `target_device` config plus model-byte estimates feed
deployment-aware scoring and the topology atlas (best graph per task family /
device class / parameter bucket / latency band / motif).

## Seeding Roles

Topograph supports three run modes — `unseeded`, `seeded` (direct Primordia
motif priors biasing initialization/search), `staged_seeded` (consume seeds
after a warmup budget fraction; also the consumer position for
Stratograph-translated priors). Modes are labeled, never hidden; an unseeded
baseline is always preserved (full contract in ch. 11).

## Telemetry (Beyond The Floor)

Topology size; novelty metrics; MAP-Elites occupancy; mutation operator
success summaries; depth/width/skip statistics; sparsity and precision
distributions; benchmark timing; archive dynamics; inheritance savings.

## What Topograph Must Avoid

Benchmark-chasing script piles; a generic trainer with evolution bolted on;
hiding cost behind one summary metric; only finding oversized graphs; being
unable to explain why one topology beat another. Not infinite graph chaos —
compact, reusable structural intelligence.
