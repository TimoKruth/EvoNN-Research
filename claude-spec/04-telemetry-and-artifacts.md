# 04 — Telemetry, Export Contract, And Output Quality

Opaque search is weak search. Every system must explain itself well enough to
survive comparison and later reuse. This chapter defines the telemetry floor,
the export contract, and the L0–L4 output-quality ladder.

## Minimum Run Metadata

Every serious run records: system name; run ID; git commit / code version
when available; config path or embedded config snapshot; start timestamp; end
or latest-checkpoint timestamp; run status (`completed`, `failed`,
`interrupted`, `resumed`, `cancelled`).

## Minimum Budget Metadata

All normalized fields from chapter 03, including pack ID, tier, declared vs
actual evaluations, evaluation-counting semantics, cached/failed/invalid
counts, resume provenance, partial/complete status, wall-time budget and
actual, hardware class, worker count.

## Minimum Seeding Metadata

The full seeding field set from chapter 03. Ladder-comparison reporting
rules: direct and staged runs MUST never merge into one anonymous "seeded"
bucket; a seeded run missing ladder metadata is marked **transfer-opaque**
and excluded from clean comparison.

## Minimum Search Telemetry

Whatever is natural to the abstraction, but at least: candidates evaluated;
best score so far; current phase/stage; archive or elite counts; failure and
invalid-candidate counts; generation/iteration count.

## Minimum Artifact Telemetry

Where supported: parameter count; model bytes / serialized size estimate;
latency estimate or measurement; memory estimate or measured peak. If a
metric is unsupported, mark it unavailable explicitly — never silently omit.

## System-Specific Telemetry Expectations

| System | Additional required telemetry |
|---|---|
| Primordia | primitive count / motif complexity; microcircuit depth/width summary; motif bank size; promotion counts into higher-fidelity stages |
| Prism | family distribution; family archive occupancy; transfer/inheritance usage |
| Topograph | topology size; novelty metrics; MAP-Elites occupancy; mutation-operator success summaries |
| Stratograph | macro depth; cell library size; reuse ratio; clone and specialization counts; motif frequency summaries |
| Contenders | contender family; configuration ID; training budget actually used |
| Compare | compared run IDs; pack ID; comparison assumptions; excluded runs / filtered artifacts; ladder labels for every seeded run; direct/staged/unseeded kept in distinct buckets |

## Resume And Failure Telemetry

Runs make it easy to tell: whether a run resumed from checkpoint; whether it
consumed prior artifacts; why it stopped; whether results are partial or
final.

## The Export Contract ("Symbiosis Export")

The standard comparison boundary is a set of files; comparison MUST work from
these files alone:

### `manifest.json`
- `system` — engine identifier (`prism`, `topograph`, `stratograph`,
  `primordia`, `contenders`; historical values `evonn`, `evonn2`, `hybrid`)
- run ID, pack ID, seed, timestamps
- budget block (all ch. 03 fields)
- runtime block — backend (`mlx` | `numpy-fallback` | …), backend version,
  device class, precision mode, worker topology, host fingerprint
- seeding block (all seeding fields)
- artifact listing — config snapshot, report markdown, optional compact
  summaries, checksums

### `results.json`
One record per (benchmark, outcome):
- canonical benchmark ID; task kind; metric name, direction, value
- status — `ok` | `failed` | `skipped` | `unsupported` (unsupported/skipped
  coverage MUST remain visible, never dropped)
- parameter count, train seconds, model bytes, memory where supported
- per-benchmark evaluation counts consumed

### `summary.json`
Canonical machine-readable run rollup: best-per-benchmark, aggregates,
budget-accounting echo, fairness-relevant flags. Shared fields are defined in
`evonn_shared` so every engine emits the same shape.

## Report Surfaces

Telemetry MUST be present in at least one of: structured summary JSON,
metrics database, markdown report, checkpoint metadata. Best case: important
metrics appear in both machine-readable and human-readable form. `report.md`
MUST be rebuildable from stored artifacts (a `report` CLI verb refreshes it
without deleting anything).

## Engine CLI Surface (Common Verbs)

Every engine exposes, minimum:

```
<engine> evolve --config <yaml> --run-dir <dir>     # run (resumable)
<engine> inspect <run-dir>                          # runtime, usage, wins, leaders, failures
<engine> report <run-dir>                           # rebuild report.md
<engine> benchmarks                                 # list resolvable benchmarks
<engine> warm-cache …                               # prepare dataset/LM caches
<engine> symbiosis export <run-dir> --pack <pack>   # emit manifest/results/summary
```

Engines with seeding roles add `seed export` (Primordia) / seed-consumption
config (Topograph, later Prism).

## Output-Quality Levels (L0–L4)

Every run's artifact set is classifiable; `evonn-compare output-quality`
identifies each run's level and the gaps to the next one.

| Level | Name | Requirements |
|---|---|---|
| L0 | Legacy | pre-contract output; not compare-grade |
| L1 | Contract | valid `manifest.json` + `results.json` |
| L2 | Comparable | + `summary.json`, fairness coverage (unsupported/skipped visible), canonical IDs |
| L3 | Measurable | + runtime/performance/diagnostic fields: wall-clock, backend, device, eval/sec, cache/reuse, failure and skipped metadata propagated into trend rows |
| L4 | Decision-grade | + repeatability: multi-seed variance, effect sizes, statistical decision labels, decision support (ch. 12) |

Standing requirements:

- All engines MUST hold L3 on Tier A and the trusted daily lane
  (`tier1_core@64`); higher trusted budgets either complete at L3 or report
  exact blockers by system and benchmark.
- Dashboards show **measurement downgrade reasons**, not only final scores.
- No system may silently undercount budget, hide failed candidates, or drop
  benchmarks from summaries.
