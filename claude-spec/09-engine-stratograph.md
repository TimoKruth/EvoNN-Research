# 09 — Stratograph: Hierarchy-First Search Engine

## Thesis

Stratograph asks: **which reusable structures should exist, where should they
repeat, and where should they diverge?** Instead of one flat DAG, it evolves
a **macro graph over a library of reusable cells**. It is the bet that
hierarchy, motif reuse, and controlled specialization can buy search
efficiency, generalization, modularity, transfer, and interpretability that
flat search cannot.

This is not "Topograph but deeper." Hierarchy is the primary search object.
If hierarchy does not matter, the project must be able to show that too —
a distinct project is how we get an honest answer.

Role in the portfolio: **hierarchy challenger**. Evidence bar: Stratograph
must show a hierarchy-specific advantage on at least one benchmark class
(current evidence: tabular / tabular-regression at upper-mid budgets), or be
downgraded to archive candidate after its planned advancement work.

## Core Model

Every candidate has two coupled levels:

1. **Macro graph** — DAG of cell instances; controls routing, skips,
   ordering, repetition, fan-in/fan-out, global information flow, and where
   reuse vs specialization pressure lands.
2. **Cell library** — reusable cell programs; each cell is a micro-graph of
   primitives, projections, merges, gates. Multiple macro nodes may point at
   the same cell.

A candidate is therefore: topology over cells + a library of motifs + the
relationships between sharing and divergence.

## Genome

`HierarchicalGenome`: macro nodes, macro edges, cell library. Each cell:
`CellNodeGene` + `CellEdgeGene` collections. Each macro node references a
cell by `cell_id`.

Validated invariants (aggressive, on every construction):

- no duplicate macro node IDs; no duplicate cell-node IDs inside a cell
- every macro node references a real cell
- macro graph acyclic; every cell graph acyclic
- macro graph reaches output

Structural metrics exposed directly on the genome: macro depth, average/max
cell depth, reuse ratio — used in reporting and evaluation heuristics.
A codec provides serialization and content digesting.

## Compilation

Genome → `CompiledHierarchy` of shared `CompiledCell` objects: topologically
order nodes inside each cell; merge multiple inputs by deterministic
projection + averaging; apply primitive activations; **reuse compiled cells**
when several macro nodes share a cell; run the macro DAG over the compiled
cell executors.

Two evaluation paths, staged by maturity:

1. **Fast proxy path** (bootstrap phase): deterministic compilation encodes
   inputs into structure-derived features; classification/image fit a
   lightweight trained head (neural GELU head with warm-start inheritance);
   LM uses a structure-conditioned scorer upgraded to a neural vocab
   projection head. Evaluates "how useful is this hierarchical
   representation?" cheaply — enough for full compare-surface participation.
2. **Full MLX trainer path** (maturity target): hierarchy-specialized
   end-to-end training with weight inheritance, matching Prism/Topograph's
   training realism. Long-horizon optimization of this path is a known open
   item; the proxy path stays available for cheap screening with honest
   fidelity-regime labels (ch. 03).

## Search Operators

Hierarchy-aware by construction — operators directly manipulate sharing and
specialization, not generic graph perturbation:

- width changes; activation changes
- **clone a shared cell** (then let descendants diverge)
- **specialize a clone** (local adaptation)
- add macro node; macro rewiring; skip-edge insertion
- motif rewrite (replace cell internals from the motif library)
- crossover: take macro segments from both parents preserving inherited
  macro edges, rebuild a child hierarchy, then mutate

### Task- and dimension-aware seed profiles (evidence-backed, keep)

- LM seeds: wider/deeper starts, sequence-oriented motifs, LM-specific
  offspring rotation (motif rewrite / macro rewiring / width-specialization /
  macro expansion), bounded survival credit for sequence primitives, reuse,
  macro depth, cell depth.
- Regression seeds: wider/deeper with regression-biased primitive mix.
- High-dimensional tabular seeds: stronger width floor, explicit tabular
  motifs, motif-backed cell internals, bounded survival credit for tabular
  motif share and cell depth.
- Image/LM profiles explicit rather than generic fallbacks.

### Negative result to respect

A broad benchmark-leader exploitation slot in reproduction was tried and
**removed** — it did not improve the aggregate signal and cost diversity.
Crossover-first diversity pressure is the default; exploitation experiments
must be bounded and evidence-gated.

## Ablation Harness (First-Class)

`ablate` / `ablate-matrix` compare, at matched budget, at minimum:
`flat` (single-level macro), `unshared` (hierarchy without sharing),
`shared` (full model), `no-clone`, `no-motif-bias`. This is how the central
claim is tested. Reference findings that shape priorities: sharing beats
unshared hierarchy broadly; motif bias helps overall; clone helps weakly;
**flat still wins absolute score on image and LM** — those are the gaps.

## Motif Mining

Extract repeated winning sub-cell structures across winners (`motifs
analyze`); cluster motifs by function; trace motif lineage through
clone/specialize events; distinguish global vs local motifs; build a motif
atlas; learn the motif library from winning runs instead of fixed priors.
Mid-term, Stratograph's output is architecture + motif + structural
explanation, not just a score.

## Scientific Questions (The Engine's Contract)

Does hierarchy buy search efficiency at equal budget? Does reuse buy
generalization? Does specialization buy accuracy? Do repeated motifs emerge?
Can motif libraries transfer across benchmark families? Which seeding ladder
works better (unseeded vs `Primordia→Stratograph` vs
`Primordia→Stratograph→Topograph`)? Where does hierarchy hurt (wasted
complexity, unstable training, brittle specialization, excessive cloning,
latency, memory)?

## Diagnostics Requirements

- **LM flatline diagnostic**: identify whether LM weakness is evaluator,
  genotype, compiler, or search-policy related; report as a structured
  artifact (feeds the registry's flatline detection, ch. 12).
- Hierarchy descriptors: macro depth, cell reuse, inter-level connectivity,
  hierarchy collapse rate, clone/specialization counts, motif frequency,
  interface width profile, novelty, occupied niches.
- Budget-adaptive hierarchy depth limits.

## Runtime Maturity Features

Resume/checkpoint/status; best-genome artifacts; failure-pattern summaries in
inspect/report; ladder workflow command for compare validation; warm-cache
and LM cache listing; backend/version metadata through exports; Linux-capable
fallback for the trust lane (ch. 13).

## What "Winning" Means

Not only benchmark score. A true Stratograph win is any combination of:
better score at same budget; better score per evaluation; parameter
efficiency; repeated discovery of useful motifs; interpretable reuse; cleaner
cross-family transfer; evidence that hierarchy compresses search into better
building blocks. Ties with reusable motifs and clear structure can still be
meaningful — but the portfolio rule (ch. 12) requires *distinct* evidence, or
downgrade.
