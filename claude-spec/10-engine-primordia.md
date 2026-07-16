# 10 — Primordia: Primitive-First Motif Discovery

## Thesis

Primordia asks: **which tiny computational motifs deserve to exist before
they are assembled into families, topologies, or hierarchical cells?** It is
the layer closest to the original intuition of genetic evolution starting
near the neuron level and growing upward — the bridge between
single-neuron/tiny-circuit evolution and the architecture-scale systems.

Good higher-level architectures may depend on low-level motifs that are
rarely hand-designed: tiny gated subcircuits, unusual merge operations,
sparse local operator patterns, activation arrangements, micro-ensembles
that beat naive neuron abstractions. If such motifs exist and can be found
cheaply, no higher-level system should have to rediscover them from scratch.

Role in the portfolio: **specialization and seed-source engine** — first
credible source for downstream seeded-vs-unseeded experiments. It is NOT a
broad generalist and must not be forced into that role; evidence shows
pockets on synthetic/regression families and image/LM-looking behavior that
requires extra scrutiny on real non-smoke benchmarks.

## Design Principles

1. **Cheap first.** Primitive-first search must be dramatically cheaper than
   architecture-scale search or it loses its strategic value. If the lane
   grows so expensive it stops being a bounded scouting function, it has
   failed its purpose. Runtime controls are mandatory: high-slot epoch caps,
   expensive-family epoch caps, cheaper mutation of weak/expensive parents,
   architecture clamps per task family (image, LM, tabular, synthetic).
2. **Explicit exportability.** Discovered motifs are versioned, exportable
   artifacts — otherwise the layer cannot contribute to cumulative memory.
3. **Benchmark discipline.** Primitive discovery still uses shared packs,
   contender expectations where appropriate, and full budget disclosure
   (budget-matched per-benchmark evaluation scheduling).
4. **No hidden merger.** Primordia stays a distinct layer. Its output can
   seed higher systems; it must not be silently buried inside them.
5. **Self-containment by deliberate duplication.** Primordia is a
   self-contained package (own MLX runtime boundary, own benchmark/parity
   loaders), even at the cost of duplicated code, recorded in a dedicated
   duplication-notes document (ch. 01, Standalone Rule).

## What Primordia Tests

- do primitive motifs improve downstream search efficiency?
- do some motifs transfer across benchmark families?
- which motifs recur under strong budget constraints?
- where does primitive complexity help vs hurt?
- can cheap low-level search discover building blocks worth preserving?

## Search Lane

- primitive genome over low-level operators/motifs (single-neuron or
  tiny-group operator variants, gated microcircuits, tiny sparse motifs,
  activation and merge patterns)
- MLX-backed candidate search (reference backend) + Linux `numpy-fallback`
  runtime for smoke/compare-grade validation; the actual backend used is
  recorded in run/export artifacts
- bounded elite/archive search with lineage-aware offspring mutation from
  archived parents
- per-benchmark and family-level leader tracking
- per-benchmark best-primitive selection

## Artifacts (The Point Of The Engine)

Beyond the standard export contract:

- **`primitive bank summary`** — ranked motif bank with diversity
  descriptors, emitted alongside run artifacts and compare exports
- **`seed_candidates.json`** — benchmark-conditioned seed candidates for
  downstream family/topology/hierarchy seeding experiments (the input to the
  ch. 11 seed artifact contract)
- **`search_leaders.json`** — per-benchmark and family-level leaders
- primitive usage, benchmark-group coverage, and failure telemetry through
  reports and exports
- markdown reports with primitive-bank winners, benchmark leaders, family
  leaders, representative genomes; `inspect` rebuilds the bank view from
  `best_results.json`/`trial_records.json` if the bank artifact is missing

## Motif Bank Lifecycle (Maturity Target)

- ranked motif bank with descriptor coverage metrics (not optimizing one
  narrow smoke pattern)
- separate "locally good" motifs from "transfers downstream" motifs
- motif aging/retirement driven by transfer evidence
- contamination-safe train/test handling for seed artifacts
- motif bank filtering on export where raw banks are too broad

## CLI

```
primordia run --config <yaml>
primordia inspect --run-dir <dir>
primordia report --run-dir <dir>
primordia seed export --run-dir <dir>
primordia symbiosis export --run-dir <dir> --pack-path <pack.yaml>
```

Canonical named configs: `smoke`, `tier1_core_eval64/256/1000`,
`tier_b_core_eval256/1000` — tier1 configs include the regression pair so the
official lane stays aligned with parity-pack coverage instead of silently
dropping regression.

## Evidence Target

Primordia must either improve downstream search through transfer
(ch. 11 proof) or be judged a specialist engine for primitive-level tasks
only. Image/LM-looking wins stay under extra scrutiny until validated on real
non-smoke benchmarks and are kept separate from broad general-engine claims.
Its known runtime risk on broad Tier C (high-slot cost) is why its
architecture clamps and epoch caps are load-bearing, not optional.
