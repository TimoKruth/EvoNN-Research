# 14 — Quality-Diversity And Multi-Objective Search

Leaderboard score-wins are necessary but insufficient. The engines must
eventually optimize tradeoffs between score, runtime, architecture
complexity, diversity, and transfer value — and produce **archives of diverse
high performers**, not single winners. This chapter defines the shared
descriptor/objective substrate and the engine-local machinery.

Design split: the **shared layer** defines candidate descriptors, optional
objective vectors, archive/report schemas, and dashboard views (Pareto
fronts, diversity coverage). The **engine-local layer** chooses descriptors
that fit its abstraction and keeps all search-core logic package-local, while
emitting comparable descriptor summaries.

## Objective Vector (Shared Schema)

Candidate objectives, engine-optional but schema-shared:

- primary benchmark metric
- evaluation cost
- architecture size (params / bytes)
- inference latency proxy
- runtime memory proxy
- novelty/diversity score
- transfer success score

## Descriptors Per Engine

| Engine | Behavior descriptors |
|---|---|
| Prism | family/operator composition; parameter count; graph depth |
| Topograph | topology shape (depth, max width, skip count); sparsity; precision profile; connectivity density; skip density; motif placement; graph edit distance from seeds |
| Stratograph | hierarchy depth; cell reuse ratio; cell library size; layer composition; inter-level connectivity; hierarchy collapse rate |
| Primordia | primitive type; motif length; descriptor coverage |

## Archive Types

- **Per-benchmark elites** — best genome per benchmark (all engines).
- **Pareto fronts** — non-dominated sets over the objective vector; minimum
  quality-vs-params in Prism; deployment-aware fronts in Topograph.
- **Novelty archive** — k-NN novelty in behavior space
  (`novelty_weight` λ blending, default 0 = off; `novelty_k`;
  `novelty_archive_size`).
- **MAP-Elites grid** — binned behavior space; best-per-cell; archive-drawn
  parents (`map_elites_selection_ratio`) reinject diversity.
- **Niche archives** — family-level (Prism) and motif/family niches
  (Primordia).
- **MOME-style multi-objective archives** — ancestral Track A capability;
  resurrection candidate once Pareto reporting is stable.

Mechanism scales (kept complementary, never merged): speciation protects
young structural innovations inside the population; novelty applies soft
pressure toward unexplored behavior; MAP-Elites gives a hard best-per-niche
diversity guarantee.

## Compare/Reporting Surface

- descriptor summaries in exports (comparable across engines)
- archive reports in Compare: occupancy, fill ratio, per-cell improvement
- Pareto-front views and diversity-coverage views in the dashboard
- QD telemetry in campaign/trend surfaces (occupied niches, archive sizes)

## Rollout Order (Evidence-Gated)

1. Optional descriptor schema in Shared.
2. Descriptor exports in one engine first — Topograph preferred.
3. Simple archive report in Compare.
4. One quality-diversity search-strategy branch in Topograph or Primordia.
5. Compare against existing search at equal budget.
6. Promote only if archive diversity improves without destroying metric
   quality.

## Acceptance Criteria

- Candidate diversity is measurable, not just described.
- Pareto/descriptor views explain why an engine is useful even when it is
  not the top scalar-score winner.
- Quality-diversity features produce evidence that changes engine strategy
  decisions (portfolio rules, ch. 12).

## Deployment-Aware Evidence (Topograph-Led)

Quality-first ranking with deployment views: quantization retention
(post-training int8/int4 profiling was proven in Track A), latency bands,
byte budgets, memory footprint. The long-run product is the **topology
atlas**: best graph per task family, per device class, per parameter bucket,
per latency band, per operator motif — archives as reusable model-family
assets and recommendation sources for future search.
