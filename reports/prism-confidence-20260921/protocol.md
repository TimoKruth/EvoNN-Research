# Prism-only version comparison — frozen design, September 21, 2026

**Prepared and preflight-verified; no study training started.** Producer commit:
`8b8c3db80774be628e1dc97971cdd446a71c348a`. The
[preparation receipt](../../governance/prism-version-confidence-20260921.json)
binds all 55 campaign manifests, 217 unique dataset splits and 232 audited
historical evidence files. [Preflight](preflight.json) passes;
[before-run status](before-run-status.json) records all 1,012 runs pending.

The user explicitly requested a comparison of **only Prism**, then chose **all
eleven variants**. This study is a named exception to the usual all-engine rule.
It evaluates Prism version differences on fixed validation workloads. It cannot
establish superiority over other engines or Contenders, protected-test quality,
or generalization to other datasets.

## Matrix and compute commitment

Variants: `legacy`, `archive`, `training`, `broad`, `open`, `search_v2`,
`representation_v2`, `regularized_v2`, `averaged_v2`, `calibrated_v2`, `frontier_v2`.

| Stage/panel | Pack | Fits per run | Epoch allowance | Seeds | Runs | Fit attempts |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Qualification, core | `tier_b_core_v2` | 32 | 2 | 21600 | 11 | 352 |
| Qualification, breadth | `language_breadth_v1` | 32 | 2 | 21600 | 11 | 352 |
| Main, core128 | `tier_b_core_v2` | 128 | 12 | 21601–21630 | 330 | 42,240 |
| Main, core256 | `tier_b_core_v2` | 256 | 12 | 21601–21630 | 330 | 84,480 |
| Main, breadth128 | `language_breadth_v1` | 128 | 12 | 21601–21630 | 330 | 42,240 |
| **Total** | | | | | **1,012** | **169,664** |

Every run uses MLX on CPU, population 4, inheritance enabled, restarted Adam and
the NumPy optimizer backend. Preset-specific search, training allocation and
architecture differences are the treatment. Actual optimizer work is reported;
equal fit counts do not mean equal compute. Each engine run has a 1,500-second
cap and each fit a 120-second cap. Runs execute serially. Main seed blocks rotate
panel order and arm order; each arm occupies each position either two or three
times per panel. No seed replacement or adaptive sample-size extension is allowed.

This is a substantial multi-day commitment. Applying only the historical
September 14 `open` core timings (170.64 seconds at 128 and 362.82 at 256) to the
660 core slots gives about **49 hours**, before breadth, qualification, replays
or new-policy overhead. This extrapolation is not a current runtime measurement
or an upper/lower bound. The language breadth and new variants could cost more.
Use bounded batches and review qualification timing before launching the main
stage; changing the design requires a new frozen protocol before main outcomes.

## Confidence and interpretation

There are 55 variant pairs. Two panels are primary, giving **110 predeclared
contrasts** in one Holm family at familywise alpha 0.05:

1. Core256: equal-weight average of seed-paired effects on digits accuracy,
   diabetes MSE and Shakespeare byte perplexity.
2. Breadth128: equal-weight average of seed-paired effects on the three real-text
   tasks (original Shakespeare, context64 Shakespeare, context64 Aesop).

Banknote is a fixed ceiling/regression sentinel. Delayed copy is a fixed temporal
memory sentinel, separated from real-text language quality. Neither is silently
dropped: every task appears in the raw report. Core128, budget scaling, individual
tasks, model size, optimizer work and timings are secondary/descriptive. A
trade-off on those tasks must be reported alongside an aggregate winner.

Each paired task effect is direction-aware `2*(after-before)/(|after|+|before|)`;
lower-is-better metrics reverse the sign. Aggregate once within each seed, then
perform inference across **30 seeds**, not across fit attempts, tasks, repeated
budgets or validation examples. The exact two-sided signed-rank calculation uses
integer subset enumeration, average ranks for ties, and discards differences
rounding to zero at 12 decimals. Its null assumes independent, symmetrically
distributed paired seed effects; see [SciPy's signed-rank documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).

A supported direction requires all three: Holm-adjusted p ≤ 0.05, mean symmetric
gain at least 1%, and a descriptive 95% paired-seed bootstrap interval excluding
zero. Bootstrap uses 20,000 resamples and fixed RNG seed 21600; these intervals
are **not simultaneous confidence intervals**. A panel has a unique supported
leader only if that variant clears the rule against every other variant.
Otherwise the result is inconclusive. Nonsignificance never establishes
equivalence, and a panel leader does not automatically become the default.

Pre-outcome sensitivity simulation (20,000 Gaussian paired samples per effect,
seed 21600) uses the conservative first-Holm threshold 0.05/110. At 30 seeds,
power before the materiality filter is approximately 13.6%, 53.5%, 89.4%, 99.3%
and 100% for mean/paired-SD effects of 0.5, 0.75, 1.0, 1.25 and 1.5. This motivates
30 rather than 16 seeds, but does not promise detection of small differences.
No new outcomes were used to choose the sample size. The frozen preparation
receipt includes the simulation and a fresh-seed audit against available local
governance/report JSON and historical campaign manifests; unrecorded external
seed use remains unknown.

All results remain validation-selected. This comparison does not access protected
test data or close the old incomplete 28/30 study. Review task-level losses and
confirm a nominated default independently before claiming broader advancement.

## Prepared execution and recovery

The preparation receipt records the exact producer commit, source hash,
environment, native backend check, dataset artifacts, manifest hashes and seed
audit. The source is a private snapshot of the maintained workspace, including
its uncommitted Prism implementation. Other packages may be present in that
snapshot, but **only Prism is scheduled**. Its separate virtual environment and
immutable campaign manifests prevent accidental adoption from a changed source.

Prepared workspace:
`.artifacts/prism-confidence-20260921/study`

Prepared producer:
`.artifacts/prism-confidence-20260921/producer`

From the maintained repository root, run only the qualification stage first:

```sh
.artifacts/prism-confidence-20260921/run.sh --qualification-only
```

After inspecting its successful completion and observed timing, the same frozen
controller can execute the full study, or a bounded batch:

```sh
.artifacts/prism-confidence-20260921/run.sh
.artifacts/prism-confidence-20260921/run.sh --max-runs 11
```

The full command automatically completes/revalidates qualification before any
new main dispatch. Re-running the command resumes verified evidence. It cannot
skip a failed arm or enlarge an exhausted budget. An orphaned complete export
is adopted without inadvertently dispatching the next seed out of order.

To pause at the next completed-run boundary:

```sh
touch .artifacts/prism-confidence-20260921/study/PAUSE
```

An active bounded run and its replay finish. Remove that file and invoke `run.sh`
again to continue. A failure stops execution and retains diagnostics. A source
fix requires a fresh replacement producer/study; do not repair frozen evidence
in place. Every qualification fit and every main fit must succeed, and every
saved winner must replay before inference can complete.

```sh
.artifacts/prism-confidence-20260921/check.sh
.artifacts/prism-confidence-20260921/analyze.sh
```

Before complete coverage, analysis reports incompleteness without statistical
testing. Final analysis revalidates journal bindings, exports and replay receipts,
then writes immutable `analysis.json` with every task/seed/variant result,
resource measures, all 110 corrected contrasts and per-panel leader decisions.
Preparation itself starts **no study training** and installs no scheduler.
