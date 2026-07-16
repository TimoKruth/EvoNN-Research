# 00 — Scope And Goals

## Mission

EvoNN exists to answer one broad question:

> How should neural architectures be discovered, compared, improved, and
> carried forward when we care about real search abstractions, real benchmark
> breadth, real budget discipline, and real local iteration?

EvoNN turns architecture search from a collection of isolated model hunts into
a **comparative discipline with memory**. The system must tell us not only
what scored highest, but:

- which search abstraction produced the result
- what budget it consumed
- what benchmarks it really covered
- what telemetry and artifacts survive outside the source run
- whether the result still matters against strong non-evolutionary baselines
- whether the result can seed stronger future searches instead of dying as an
  isolated checkpoint

## The Seven Thesis Claims

The whole design follows from these claims. Every chapter of this spec is an
operationalization of one or more of them.

1. **Shared packs, not one-off demos.** Neural architecture search must be
   evaluated across shared benchmark packs with canonical identities.
2. **Distinct abstractions, kept distinct.** Different search abstractions
   (primitive, family, flat topology, hierarchy) must stay genuinely separate
   long enough to teach us something real. Later merging is only meaningful if
   the sources were isolated first.
3. **Strong baselines or no claims.** Baselines must be strong enough that
   evolutionary wins mean something. A win over a toy baseline is not a win.
4. **Artifacts are the product.** Exports, manifests, reports, telemetry, and
   budget accounting matter as much as raw scores.
5. **Local-first is strategic.** Bounded local experimentation (Apple Silicon
   first, Linux-portable) makes iteration, reproduction, and comparison
   practical. A laptop-scale run that teaches something real beats a
   cluster-scale run that cannot be reproduced.
6. **Structure compounds.** Structure discovered at lower levels must be
   allowed to seed higher levels rather than being discarded between
   experiments — and that seeding must itself be measured, not assumed.
7. **Hard benchmarks are the north star, not the daily diet.** The target is
   any benchmark surface where neural systems might discover surprising,
   competitive solutions — climbed via a disciplined ladder, not leapt at.

## System Inventory

Foundation layers:

| Layer | Package | Role |
|---|---|---|
| Benchmarks | `shared-benchmarks/` | Canonical benchmark identities, catalogs, packs, LM caches |
| Trust | `EvoNN-Compare` | Fair-matrix execution, trends, dashboards, audits, evidence registry, decision gate |
| Floor | `EvoNN-Contenders` | Strong fixed non-evolutionary baselines exported in the shared contract |
| Substrate | `EvoNN-Shared` | Contracts, budget/telemetry/seeding models, manifest helpers, narrow training preprocessing |

Search bets (each a distinct scientific claim):

| Engine | Package | Primary question |
|---|---|---|
| Primordia | `EvoNN-Primordia` | Which low-level computational motifs deserve to exist before assembly into larger systems? |
| Prism | `EvoNN-Prism` | Which model family should solve this task, and how should it be parameterized? |
| Topograph | `EvoNN-Topograph` | Which flat DAG of learned operators should solve this task under real hardware constraints? |
| Stratograph | `EvoNN-Stratograph` | Which hierarchy of reusable, specializable cells should solve this task? |

Operating roles (evidence-derived; revisited by the portfolio rules of
chapter 12):

- **Prism** — default day-to-day operating engine; strongest low-budget
  generalist in promoted evidence.
- **Topograph** — first serious challenger; strongest at converting higher
  budgets in engine-only cohorts; budget/profile-sensitive.
- **Stratograph** — hierarchy challenger; strongest on tabular/regression
  families at upper-mid budgets; seed-volatile; must prove hierarchy adds
  something distinct.
- **Primordia** — specialization and seed-source engine, not a broad
  generalist. Its value is cheap low-level structure.
- **Contenders** — external floor; in current evidence it dominates broad
  Tier C, which is exactly the honest pressure the platform needs.

## What Success Looks Like

EvoNN succeeds if it produces:

- fair comparisons that people can actually trust
- strong baseline coverage that rules out easy self-deception
- clear evidence about the strengths and limits of each engine
- reusable exports, reports, benchmark contracts, and telemetry surfaces
- at least one engine that beats or ties the required contender floor on a
  meaningful subset of non-smoke benchmarks under repeated evidence
- at least one transfer/seeding path proven useful, proven harmful, or
  formally classified inconclusive with enough evidence to guide strategy
- a path toward a later combined system built from proven wins instead of
  intuition alone

## Explicit Non-Goals

The system MUST NOT be used to justify:

- a giant rewrite that merges all engine search cores prematurely
- adding many benchmarks before floors and repeated evidence exist
- claiming transfer success from metadata-only (portable-plumbing) runs
- presenting Linux fallback results as equivalent to MLX-native evidence
- optimizing runtime without measuring quality and budget effects
- continuing to invest equally in every engine indefinitely without
  portfolio decisions
- weakening contenders to make the engines look better
- treating Tier A/smoke wins as broad capability evidence
- hiding evaluation reductions, cached work, or partial runs in reports

## Research Lineage (External)

The design deliberately borrows established patterns; implementers should be
familiar with:

- **NAS-Bench-101 / NAS-Bench-201** — reproducible benchmark surfaces and
  fixed search/evaluation rules for NAS claims
- **OpenML / AutoML Benchmark** — shared tasks, run metadata, and reusable
  benchmark definitions
- **MLPerf** — benchmark rules, system metadata, quality targets, separated
  scenarios for heterogeneous systems
- **Demšar (2006)** — statistical comparison of classifiers over multiple
  datasets; one run on one benchmark is never enough
- **MAP-Elites / quality-diversity** — archives of diverse high performers,
  not just a single best candidate
- **NSGA-II / multi-objective NAS** — accuracy, runtime, memory, complexity,
  and search cost as explicit objectives

## Glossary

| Term | Meaning |
|------|---------|
| **Engine** | One of the four search systems (Primordia, Prism, Topograph, Stratograph) |
| **Genome** | A searchable candidate representation, engine-specific |
| **Family** | A model template class (mlp, conv2d, attention, …) — Prism's search object |
| **Benchmark** | A dataset + task + metric combination with a canonical ID |
| **Pack / suite** | A named, versioned collection of benchmarks |
| **Ladder tier (A–E)** | Difficulty/purpose tier of a benchmark pack (ch. 02) |
| **Lane** | A named recurring (pack, budget) combination used for evidence |
| **Budget** | Declared comparable resource envelope, primarily evaluation count (ch. 03) |
| **Contender** | Fixed non-evolutionary baseline (ch. 06) |
| **Contender floor** | The score bar set by required contenders on a benchmark |
| **Fair matrix** | Compare's orchestrated run of all systems on the same pack/budget/seed (ch. 05) |
| **Trend row** | Structured longitudinal record of one (engine, benchmark, budget, seed) outcome |
| **Evidence registry** | Durable, append-only store of promoted comparison runs (ch. 12) |
| **Output level L0–L4** | Artifact quality ladder from legacy to decision-grade (ch. 04) |
| **Lane operating state** | `contract-fair`, `trusted-core`, `trusted-extended`, or explicit exploratory (ch. 05) |
| **Seed artifact** | Versioned export of discovered structure for downstream consumption (ch. 11) |
| **Seeding ladder** | `none`, `direct` (Primordia → X), or `staged` (Primordia → Stratograph → Topograph → Prism) |
| **Elite** | Best genome for a specific benchmark |
| **Niche / MAP-Elites cell** | A quality-diversity archive slot keyed by behavior descriptors |
| **Motif** | Reusable low-level or cell-level structure discovered by search |
| **Warm start / weight inheritance** | Initializing a child model with parent weights |
| **Multi-fidelity** | Reduced training budgets in early generations, with honest labels |
| **Ceiling tie** | Multiple systems hitting a metric's natural maximum; not evidence of superiority |
| **Floor clear** | An engine beating the required contender floor on a benchmark |
