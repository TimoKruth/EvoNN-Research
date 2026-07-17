# EvoNN — Full System Specification ("claude-spec")

**Status:** Draft for review
**Date:** 2026-07-16
**Kind:** Greenfield rebuild specification
**Provenance:** Distilled from the complete `Evo Neural Nets` research
superproject — its vision documents, contracts, execution plans, promoted
evidence, per-package architecture, and all deprecated tracks (EvoNN Track A,
EvoNN-2 Track B, EvoNN-Symbiosis). This spec is written so that a fresh
implementation of the entire program can be built from it, while carrying
forward every idea the project has explored.

## What This Spec Describes

EvoNN is a **local-first, benchmark-disciplined research platform for
discovering reusable neural structure across multiple architecture-search
abstractions**. It is not one NAS engine. It is a coordinated research stack:

- three **foundation layers** — shared benchmarks, a comparison/trust layer
  (Compare), and a strong fixed-baseline layer (Contenders)
- four **search bets** — Primordia (primitive-first), Prism (family-first),
  Topograph (flat-topology-first), Stratograph (hierarchy-first)
- a **shared substrate** (Shared) of contracts, budget/telemetry models, and
  export helpers
- an **evidence loop** that decides, from repeated fair measurement, which
  ideas deserve to survive, transfer upward, specialize, merge, or retire

## Chapter Index

Read in order for a full picture; each chapter is also self-contained enough
to implement against.

| # | File | Contents |
|---|------|----------|
| 00 | [00-scope-and-goals.md](./00-scope-and-goals.md) | Mission, thesis, success criteria, non-goals, glossary |
| 01 | [01-system-architecture.md](./01-system-architecture.md) | Monorepo layout, package boundaries, unification policy, tech stack |
| 02 | [02-shared-benchmarks.md](./02-shared-benchmarks.md) | Benchmark catalog, canonical IDs, packs, the Tier A–E ladder, admission gates |
| 03 | [03-budget-and-fairness.md](./03-budget-and-fairness.md) | Budget contract, accounting policy, fair-comparison rules |
| 04 | [04-telemetry-and-artifacts.md](./04-telemetry-and-artifacts.md) | Telemetry floor, export contract, run artifacts, output-quality levels L0–L4 |
| 05 | [05-compare.md](./05-compare.md) | Compare layer: fair-matrix, trends, dashboards, audits, decision gate |
| 06 | [06-contenders.md](./06-contenders.md) | Fixed baseline zoo, floor adequacy, official lanes |
| 07 | [07-engine-prism.md](./07-engine-prism.md) | Prism: family-first search engine |
| 08 | [08-engine-topograph.md](./08-engine-topograph.md) | Topograph: topology-first search engine, mixed precision, QD |
| 09 | [09-engine-stratograph.md](./09-engine-stratograph.md) | Stratograph: hierarchy-first search engine, motifs, ablations |
| 10 | [10-engine-primordia.md](./10-engine-primordia.md) | Primordia: primitive-first motif discovery and seed source |
| 11 | [11-seeding-and-transfer.md](./11-seeding-and-transfer.md) | Seeding ladders, seed artifact contract, transfer proof protocol |
| 12 | [12-evidence-and-statistics.md](./12-evidence-and-statistics.md) | Evidence registry, L4 statistical layer, engine portfolio rules |
| 13 | [13-runtime-portability.md](./13-runtime-portability.md) | MLX truth path, Linux fallback, backend honesty, CI matrix |
| 14 | [14-quality-diversity-and-multiobjective.md](./14-quality-diversity-and-multiobjective.md) | Descriptors, archives, Pareto/multi-objective evidence |
| 15 | [15-observability-and-dashboards.md](./15-observability-and-dashboards.md) | Fair-matrix dashboard, Evidence Explorer, Observatory web UI, autoresearch loops |
| 16 | [16-legacy-tracks.md](./16-legacy-tracks.md) | Full spec of the ancestral tracks (EvoNN A, EvoNN-2 B, Symbiosis, Hybrid) and what they teach |
| 17 | [17-roadmap-and-horizons.md](./17-roadmap-and-horizons.md) | Horizons, build phases, workstreams, definition of done |
| 18 | [18-engineering-standards.md](./18-engineering-standards.md) | Repo/git/PR policy, CI, testing, documentation policy |
| 19 | [19-product-interop.md](./19-product-interop.md) | Export surfaces and obligations toward the claudex-spec product track |

## Normative Language

- **MUST / MUST NOT** — hard requirement; violating it breaks the trust model.
- **SHOULD / SHOULD NOT** — strong default; deviations need a recorded reason.
- **MAY** — allowed design freedom.

## The One-Paragraph Summary

Define a fair benchmark surface; define a bounded budget contract; propose a
search abstraction; run it on shared packs; export reproducible evidence;
compare it against strong peers and contenders; keep what survives honest
comparison; carry reusable structure upward when the evidence justifies it.
That loop, operationalized, is the entire system.
