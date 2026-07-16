# 07 — Prism: Family-First Search Engine

## Thesis

Prism asks: **which model family should solve this task, and how should that
family be parameterized?** It searches inside a curated menu of architectural
templates instead of inventing arbitrary graphs — the cleanest test of
whether family choice plus disciplined family-level evolution is enough to
produce strong, general, local-first results.

Role in the portfolio: **reference engine** — the default operating engine
for routine work, and the strongest low-budget generalist in promoted
evidence. If Prism stops being the strongest general EvoNN engine on Tier B
and broad admitted Tier D, the plan must explicitly downgrade it.

Long-run north star: a local-first evolutionary model discovery engine — a
machine for building **model lineages**, not just isolated winners; an
"evolutionary operating system for model-family discovery on local hardware."

## Genome

Prism evolves immutable `ModelGenome` records (Pydantic, frozen).
`genome_id` = content hash of the serialized genome (deterministic,
content-addressed).

Fields (the union of both generations of the family engine — implement all):

```
family: str                    # one of the family registry
hidden_layers: list[int]
activation: str                # relu | gelu | tanh | silu
dropout: float                 # 0.0–0.3
residual: bool                 # MLP families only
activation_sparsity: float     # sparse families
learning_rate: float           # per-genome LR
kernel_size: int               # conv families
embedding_dim: int             # text/attention families
num_heads: int                 # attention families
norm_type: str                 # none | layer | rms | batch (searchable)
weight_decay: float            # AdamW decay (evolvable)
num_experts: int               # moe families (2, 4, 8)
moe_top_k: int                 # moe families (1, 2)
position_encoding: str         # none | sinusoidal | rope (attention families)
```

Backward compatibility across schema evolution is handled by Pydantic
validators (the ancestral `layer_norm: bool` → `norm_type` migration is the
model to follow).

## Family Registry

MLX `nn.Module` implementations, validated for family/modality compatibility
by the compiler:

- Tabular: `FlexMLP`, `SparseMLP`, `MoEMLP`
- Image: `ImageConvNet`, `LiteImageConvNet` (+ depthwise-separable variants)
- Sequence: `SequenceConvNet`, `LiteSequenceConvNet`, `SequenceGRUNet`
- Text/sequence: `TextEmbeddingModel`, `AttentionEncoderNet`,
  `SparseAttentionNet`
- State-space family group (`state_space`, `sparse_state_space`,
  `gated_state_space`) and `causal_transformer` (GQA, searchable FFN ratio)
  are proven ancestral families and SHOULD be carried into the registry.

The compiler enforces a compatibility matrix (family × modality); image conv
families only for image tasks, language modeling restricted to
embedding/attention families, etc. New families are added by: module class →
registry lists → compatibility matrix → compile branch → family-specific
crossover handling → tests. The search space must grow by adding principled
building blocks, not by rewriting the engine.

## Runtime Layers

1. **Genome layer** — immutable genome, mutation, crossover.
2. **Family layer** — module implementations + compiler (validate, then
   instantiate).
3. **Pipeline layer** — generation state, benchmark selection, evaluation,
   archive building, reproduction.
4. **Run boundary** — per-run DuckDB, checkpoints, markdown/symbiosis export.

## Evolution Loop

1. Seed population ensuring **family diversity** (never a single-template
   start).
2. Select benchmarks with extra focus on undercovered benchmarks
   (`undercovered_parent_bias`).
3. Compile each genome to MLX.
4. Optionally transfer inherited weights from parents (warm start): parent →
   family fallback → checkpoint chain; cross-family transfer allowed between
   compatible family groups (mlp↔sparse_mlp↔moe_mlp; conv variants;
   attention↔sparse_attention; state-space variants), same-family strongly
   preferred.
5. Train and evaluate on selected benchmarks.
6. Build archive views: per-benchmark elites; Pareto front (quality vs
   parameter count); family-level niche archive.
7. Reproduce: tournament selection, crossover (splice + uniform modes,
   adaptive rate by observed operator quality), single-step mutation
   (domain-aware, no-op-avoiding; includes network-morphism ops
   `morph_widen` / `morph_deepen`).
8. Checkpoint state (`state.json`) and persist metrics each generation.

## Training And Evaluation

- AdamW; cosine or constant LR schedule (warmup optional); gradient
  clipping; validation-based early stopping; wall-time caps; NaN detection.
- Multi-fidelity training schedule across generations (reduced epochs early,
  honest budget labels).
- Optional promotion screen: early generations evaluate on a benchmark
  subset and prune weak candidates before full fan-out (budget-accounted).
- Weight-inheritance cache with hit-rate telemetry.
- Regression tasks use the shared target scaling + final affine calibration
  helpers from `evonn_shared.training` (this removed a major raw-target
  regression failure mode; MUST be preserved).
- Quality semantics: classification → accuracy; regression → negative MSE;
  language modeling → negative perplexity.
- Benchmark-profile epoch scaling: deterministic per-task-profile training
  allocation (image classification, OpenML classification/regression,
  tabular regression) — changes training allocation only, never candidate
  counts or output contracts.

## Search-Quality Priorities (Evidence-Driven)

- Family-aware budget/candidate allocation — convert added budget into
  reliable Tier B/C gains (Prism's known weakness is broad-lane scaling).
- Search-space diagnostics: attribute each gain to family/operator.
- Pareto scoring over quality, runtime, size, complexity (ch. 14).
- Low-fidelity pruning only with honest budget accounting.
- Seed-consumption path (`Primordia → Prism`) after the Topograph transfer
  path validates the contract (ch. 11).

## Telemetry (Beyond The Floor)

Family distribution per generation; family archive occupancy; per-family
wins/survival by benchmark; mutation/crossover operator quality stats;
warm-start hit/miss; evaluation-cache hits; promotion screen counts.

## What Prism Must Avoid

A benchmark-specific bag of hacks; a monolithic opaque framework; score
chasing with weak evidence trails; cluster-first drift; closed formats; and
collapsing into a single-family optimizer pretending to be general NAS. If
family diversity is ever reduced to a single-template tuning loop, Prism
stops answering its research question.
