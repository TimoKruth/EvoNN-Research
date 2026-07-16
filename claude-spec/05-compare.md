# 05 — Compare: The Trust Layer

`EvoNN-Compare` is the protocol-first comparison layer and the place where
EvoNN answers: which system actually won under the same pack and budget? How
broad was the win? What evidence survives outside the source repo? What is
robust enough to trust, reproduce, and challenge?

Without Compare, EvoNN is a collection of interesting codebases. With it, it
is a comparative research program with memory.

## Responsibilities

- orchestrate fair multi-system runs (fair-matrix, campaign)
- validate exports against the contract; check budget parity and fairness
- produce longitudinal trend artifacts and dashboards
- audit benchmark packs; enforce contender-floor context
- classify output quality (L0–L4) and lane operating states
- own seeded/transfer comparison surfaces
- own the promoted evidence registry (ch. 12)
- own the performance-baseline measurement workflow
- feed the research decision gate

Compare MUST NOT import engine internals, alter scoring semantics per engine,
or grow into a giant engine-specific adapter pile.

## CLI Command Surface

```
evonn-compare fair-matrix        # orchestrated multi-system comparison run
evonn-compare campaign           # two-system (default lane) campaign with manifest
evonn-compare workspace-report   # rebuild trends + dashboard without rerunning engines
evonn-compare trend-report       # merge/query trend datasets with filters
evonn-compare dashboard          # static HTML dashboard over workspaces/summaries
evonn-compare benchmark-audit    # pack admission audit (blockers, floors, ceilings)
evonn-compare output-quality     # L-level classification of runs
evonn-compare performance-baseline  # measurement bundles for optimization work
evonn-compare compare            # ad hoc pairwise run-dir comparison
evonn-compare seeded-compare     # canonical seeded-vs-unseeded control lane
evonn-compare transfer-regimes   # none/direct/staged transfer regime runner
evonn-compare historical-baseline   # import prior campaign into live workspace
evonn-compare evidence promote|report|validate   # promoted evidence registry
```

### fair-matrix

Runs every participating system (Prism, Topograph, Stratograph, Primordia,
Contenders) on one pack × budgets × seeds grid, one **case** per
(pack, budget, seed) combination.

- Defaults: with no `--pack`/`--preset`, use the trusted daily `local` lane
  (`tier1_core @ 64`). With `--pack` but no preset, take the default budget
  from the pack's declared `budget_policy.evaluation_count`.
- Flags: `--preset`, `--seeds`, `--budgets`, `--workspace`,
  `--reset-workspace`, `--no-contenders`, `--open` (land on the dashboard),
  `--no-open`.
- Repeated runs into the same workspace **accumulate** trend data by default;
  `--reset-workspace` is for intentionally fresh starts only.
- Engine-only runs (`--no-contenders`) are for parity/portfolio reading;
  contender-including runs are for external-floor claims. The two MUST NOT be
  conflated.

### Preset ladder

Named presets bind pack + budget:
`smoke`→`tier1_core_smoke@16`; `local`→`tier1_core@64`;
`overnight`→`tier1_core@256`; `weekend`→`tier1_core@1000`;
`tier_a_smoke`/`tier_a_contract`; `tier_b_local|overnight|weekend` (compact);
`tier_b_*_v2` and `_v2_cumulative` (96/384/768/1536; 98/392/784/1568);
`tier_c_local|overnight|extended|weekend` and `_cumulative`
(128/512/1024/2048; 132/528/1056/2112);
`tier_d_local|broad|overnight|weekend` and `_cumulative`
(200/400/800/1600; 216/432/864/1728).
A preset is only added once stable runtime evidence exists for its budget.

## Workspace Layout

```
<workspace>/
├── packs/                       # budget-stamped compare packs generated per case
├── runs/                        # per-system run directories per case
├── logs/
├── reports/<case>/
│   ├── fair_matrix_summary.md / .json     # per-case canonical summary
│   ├── lane_acceptance.json               # artifact completeness, pairwise fairness,
│   │                                      # task coverage, budget & seed consistency
│   ├── trend_rows.json / trend_report.md
│   └── fair_matrix_trends.jsonl
├── trends/
│   ├── fair_matrix_trend_rows.jsonl       # append-only workspace trend dataset
│   └── fair_matrix_trends.md / .json      # longitudinal report (lane accounting +
│                                          # repeatability state surfaced directly)
├── baselines/<label>/                     # imported historical cohorts
├── seed_artifacts/                        # transfer lanes
├── performance_baselines/<stamp>-<sha>/   # measurement bundles
└── fair_matrix_dashboard.html / .json     # canonical dashboard
```

Minimum longitudinal fields per trend row: engine, benchmark, pack, budget,
seed, outcome status, metric direction/value, fairness metadata — plus
runtime/performance telemetry (wall-clock, evals/sec, seconds/success,
score/sec) and, when seeded, full seed provenance.

## Lane Operating States

A lane is never just "trusted"; name the state:

| State | Meaning |
|---|---|
| `contract-fair` | budgets/parity checks pass; artifact contract satisfied |
| `trusted-core` | + required contender floor participating and complete |
| `trusted-extended` | + extended coverage complete; decision-grade artifacts |
| exploratory / reference | explicitly labeled non-decision states |

Alongside: **accounting state** (budget truth) and **repeatability state**
(seed coverage). All three appear in trend markdown and dashboards; budget
drift must be visible from the default human review surface.

## Winner Semantics

- Per benchmark, per case: rank systems by metric (direction-aware).
- **Full-system** views include Contenders; **projects-only** views recompute
  winners with contenders removed. Both are primary recurring review views.
- Ceiling ties are counted as ties, listed separately, and never counted as
  superiority evidence.
- Failures/missing results are never silently treated as losses of the other
  side; they are visible categories.
- Win-credit aggregates may fractionally split ties (win-credit means), but
  raw win/tie/fail counts stay available.

## Dashboard (Static)

Generated as one HTML file + JSON payload beside it. Required content:

- five-system benchmark-winner tables and projects-only winner tables
- aggregate leaderboards across all discovered runs
- multi-seed aggregate evidence: score spread, confidence intervals,
  pairwise seed deltas
- per-seed aggregate snapshots (so noisy wins are not mistaken for stable)
- lane health by budget: operating/accounting/repeatability states
- runtime/performance table: wall-clock, evals/sec, sec/success, score/sec,
  family runtime allocation
- **Evidence Explorer**: normalized engine score plotted over budgets or run
  cases, filterable to benchmark or task kind, raw metrics inspectable
- recent full-run budget overview (last 10–20 comparison runs)
- transfer section: seed mode/source/artifact provenance where present

Named dashboard slices (used by the decision gate): `Overall Leaderboard:
Projects Only`, `Aggregate Evidence: Projects Only`, `Per-Seed Aggregate
Snapshots: Projects Only`, `Engine Rank By Benchmark Family: Projects Only`,
`Benchmark Trend View`, plus all-systems variants.

## benchmark-audit

Validates a pack for decision-grade use: required contender-floor metadata
present; ceilings/directions explicit; cache validation for generated data;
runtime class; admission status (`passed` / `exploratory` / blockers listed).
No pack enters a decision-grade lane without a green audit.

## historical-baseline

Imports one or more prior fair-matrix summary directories into
`workspace/baselines/<label>/`, annotating imported trend rows with
comparison cohort, label, case ID, source path, compatibility and integrity
metadata, then rebuilds trends + dashboard from the merged evidence. Seed IDs
are preserved exactly; overlapping numeric seeds stay separate via
`comparison_case_id`/`comparison_label`. This is for workspace-local
before/after review; durable memory is the evidence registry.

## performance-baseline

Builds measurement bundles for optimization work: refreshes output-quality
artifacts, applies quality/fairness gates, requires the canonical multi-budget
set (64/256/1000) before a system is claim-ready, writes
`performance_baseline.json/.md` + `run_records.jsonl` including wall-clock
medians, evals/sec, quality/sec, benchmark throughput, failure-adjusted
throughput, cache reuse rate, backend/hardware labels, and excluded runs with
explicit gate reasons. Workflow: baseline → one change → identical remeasure →
accept/scrap/inconclusive (ch. 17, Workstream 6).

## Research Decision Gate

Advancement claims are judged from linked artifacts, not chat interpretation.

**Default evidence surface**, in order: `trends/fair_matrix_trends.md`,
`trends/fair_matrix_trends.json`, `fair_matrix_dashboard.html/.json`,
case-local `reports/<case>/fair_matrix_summary.md/.json`.

**Required evidence bundle** on every engine-advancement PR: workspace path;
trend report path; dashboard path; comparison labels; exact case IDs; exact
run IDs for the changed engine and main comparison engines; exact dashboard
slices reviewed; pack/budget/seed set; lane operating + accounting +
repeatability states; one decision category.

**Decision categories** (exactly one primary), with precedence when several
apply: 1 `Tier 1 regression` (blocks promotion — trusted-lane regression
outranks any Tier B win) → 2 `needs more seeds` (single-seed or noisy
multi-seed) → 3 `Tier B-only gain` (valid research signal, not default-lane
advancement) → 4 `regress` → 5 `promote` → 6 `inconclusive`.

**Review workflow**: refresh workspace artifacts (or `workspace-report`);
import the baseline when branch-relative; record exact IDs; check lane health
before reading winners; read the dashboard slices in fixed order; check the
claimed win matches the branch thesis (intended families improved? failures
increased? Tier B only, or also `tier1_core`? repeated across seeds?); write
the decision-gate summary block in the PR.

Non-negotiable rules: no promotion from Tier B evidence alone; no hiding
`tier1_core` regressions behind broader pack wins; no citing a dashboard
without naming the slice; no citing a summary without case/run IDs; no
merging engine-advancement PRs without a stated decision category.
