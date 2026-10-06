# Topograph mixer integration and all-engine comparison — September 29, 2026

Authorization: “So we should implement the winning parts and then move on
comparing against other engines. Please do that.” This is a new all-engine
comparison, not an amendment of completed Topograph evidence.

## Integrated configuration

`evonn-topograph run --preset mixer` and `EvoNN-Topograph/configs/mixer.yaml`
select the exact confirmed policy: `variant=next`, mixer language adapters,
progress allocation, cost-aware near-tie selection, local mutations, inheritance,
0.1 crossover, 1% quality tolerance, 500,000 parameters, 0.05 label smoothing,
matrix weight decay, patience 3 and validation batch size 128. The compiler,
search and training code match the completed confirmation producer. There is
no new task routing or untested hybrid policy. Named `next`, `open` and `legacy`
presets remain available. Historical implicit defaults and replay identities
are unchanged. Mixer is the selected candidate for new comparisons, not a claim
of universal task dominance.

The preceding 19-arm screen and 16-seed confirmation found aggregate gains over
legacy/open/next but a substantial delayed-copy regression. Mechanisms other than
the adapter restriction were not separately established as causal improvements.
The new experiment therefore carries the whole confirmed configuration forward.

## Frozen execution design

The executable protocol is `evonn_compare.topograph_cross_engine.POLICY`.
Every cell contains Prism, Topograph, Stratograph, Primordia and Contenders.

- Packs: `tier_b_core_v2` and `language_breadth_v1`, including every task and the
  duplicated Shakespeare-byte observation (the duplicate is descriptive only).
- Qualification: seed 52901, 16 fits, 12 epochs, both packs, all five systems:
  10 runs / 160 fits. Complete exports and native winner replay gate main work.
- Main comparison: seeds 53001–53016, 128 fits, 12 epochs, both packs, all five
  systems: 160 runs / 20,480 fits. Total: 170 runs / 20,640 fits.
- All native engines: MLX CPU, population 4, one training worker. Contenders:
  CPU required fixed pool, optional enhanced families disabled.
- Explicit controls: Prism `open`; Stratograph `shared` legacy; Primordia
  `breadth_v2` with v2 architecture/optimization/proposals. These are maintained
  default configurations, not assumed winners of still-unfinished variant studies.
- Equal run cap 1,740 seconds and fit cap 120 seconds across all systems. The
  smaller 128-fit budget supports bounded execution; conclusions are explicitly
  at 128 fits, whereas prior within-Topograph confirmation used 256.
- Deterministically shuffled pack/system order within paired-seed blocks.
  Native checkpoints every 32 fits permit pause/resume. Contenders complete one
  bounded run at a time and have no incomplete-run retry contract.
- An isolated clean snapshot freezes source, dependency versions, host,
  benchmark/pool definitions, train/validation caches and all settings. Existing
  studies, source checkout changes and historical results remain preserved.

## Analysis and failure gates

Four predeclared mixer-versus-control aggregate contrasts use the previous
equal weights for image accuracy, diabetes MSE and real-text language quality;
real text splits its third equally among core Shakespeare-byte, breadth
Shakespeare-context64 and Aesop-context64. Banknote remains descriptive.

Four additional delayed-copy contrasts use the same paired seeds. All **eight**
tests share one Holm correction at .05 and 99.375% simultaneous percentile
bootstrap intervals (32,768 resamples, RNG 0). Effects are direction-aware
`2*(candidate-control)/(abs(candidate)+abs(control))`, with zero/zero defined as
zero. A confirmed material gain/regression requires adjusted p ≤ .05 and the
simultaneous interval entirely above +1% / below −1%. No optional stopping,
seed additions or tuning after inspection. Aggregate gain cannot be presented
as memory improvement. Full per-task means and observed costs are descriptive.

Every required family must pass Contenders admission. Its comparator is the
best successful required-pool outcome for each task; this is a bounded baseline,
not a claim of state-of-the-art adequacy. Cross-engine case validation checks
matched budgets, seed regimes, datasets and shared native runtime policy.

Any failed/missing run, corrupted provenance, failed native replay or incomplete
qualification stops execution and blocks inference. Failed evidence is retained;
no engine/seed is omitted or silently retried. Source or protocol repairs require
an explicit recorded continuation or fresh experiment. Final inference follows
full export/data revalidation. No protected tests, automatic engine promotion,
causal mechanism claims, equal-compute claims or universal ranking follow.

## Operation

The launch receipt records the isolated producer and exact snapshot. Planned
base: `.artifacts/topograph-cross-engine-20260929/`. The `studyctl` launcher
supports `preflight`, `run`, `pause`, `resume`, and `report`; status is
`study/status.json`. `PAUSE` stops future dispatches at a committed boundary.
The persistent job uses `caffeinate -i -m`, launchd Standard process priority,
and no automatic restart after a failure. Final outputs are `study/report.json`
and `study/report.md`, with every engine and task included.
