# Next staged research study — prepared, not started

This study follows the September engine refresh: Stratograph, Topograph and Primordia improved quality, while Prism traded weaker image/regression performance for better, smaller language models. More training work contributed to the gains. The next study separates mechanisms, tests independent seed cohorts, measures quality under common compute limits, and extends the language surface.

The protocol is [next-research-study-20260914.json](next-research-study-20260914.json). Current policies are based on engine revision `2715213f751f08b5b2b10ab3ddb9b8ef96bf0057`. Any prerequisite code must be reviewed and merged before freezing the actual execution producer. This document is a research and implementation plan, not a declaration that all launch gates have passed.

## Full staged matrix

Every row runs **Prism, Topograph, Stratograph, Primordia and Contenders** for every declared arm/pack/regime/seed combination. The prior engine-only exception remains specific to the completed comparison.

| Stage | Question | Design | Runs | Fit-attempt ceiling |
| --- | --- | --- | ---: | ---: |
| Q: qualification | Are execution, timing, recovery and breadth baselines trustworthy? | Core at 128/256 on two seeds; breadth at 64 on two separate seeds; reference policies | 30 | 4,480 |
| A: mechanisms | Which policy components help or harm? | Core at 128, six fresh paired seeds, eleven arms | 330 | 42,240 |
| B: confirmation | Do the nominated changes hold on untouched seeds? | Core at 128, twelve fresh seeds, current reference and selected bundle | 120 | 15,360 |
| C: measured compute | What quality is achieved under common training-time ceilings? | Core, twelve separate seeds, two arms, 10/30 training seconds per task; 256-proposal ceiling | 240 | 61,440 |
| D: breadth | Do gains survive longer contexts and another corpus? | Four-task language pack at 128, twelve separate seeds, two arms | 120 | 15,360 |
| **Maximum** | | | **840** | **138,880** |

There are up to **2,688 native winner replays**. Profiled repeats use a separate qualification allowance of at most 20 runs / 3,840 fits; they are not scientific replicates. Totals can decrease under the predeclared no-nomination rule. Compute-limited runs may consume fewer fits than their ceiling.

Only Q is first in execution order. A requires Q-core; B requires a frozen nomination from A. C additionally needs a new measured-budget contract. D requires successful breadth qualification and confirmation. Do not launch all stages as an unchecked batch.

## Reference policies and controls

- Prism: `open`, inheritance enabled, optimizer restart, NumPy optimizer backend, no imported finalists or prior weights.
- Topograph: `open`, no legacy benchmark pooling or novelty scalar.
- Stratograph: shared trainable hierarchy v2, RMS normalization, compatible inheritance, diverse selection, representation evolution enabled; no screening.
- Primordia: `breadth_v2`, width 48, depth 8.
- Contenders: frozen enhanced pool, including the relevant CatBoost, small CNN and tiny Transformer models. Required-floor, named-model and full-pool outcomes stay separate. Missing dependencies or skipped required experimental baselines block the stage.

Use locked dependencies, MLX native CPU for the four engines, population four, at most twelve epochs, one fit worker, a 1,500-second run bound and a 90-second fit bound. Contenders retains its explicit backend and per-model settings; do not pretend all five use identical optimization algorithms. Install the qualified environment with `uv sync --locked --all-packages --group dev --all-extras` in an isolated producer; record actual resolved versions before dispatch.

Rotate both arm and engine order over seeds, reversing on alternate budget regimes. Record host load, sleep events and active invocation time. Each slot starts with fresh state and weights; there is no cross-arm inheritance. Repeated unchanged-engine controls provide execution context, not extra independent seeds to pool.

## A: exact mechanism contrasts

The eleven execution arms are the refresh reference, four Prism variants, and six Stratograph controls. Only the named target engine changes in each treatment; the other engines and Contenders still execute.

| Target | Reference → treatment | Interpretation |
| --- | --- | --- |
| Prism | `legacy` → `archive` | Archive/protected-lineage policy group |
| Prism | `legacy` → `training` | Training-allocation policy group |
| Prism | `legacy` → `broad` | Broader proposals and composition policy group |
| Prism | `legacy` → `open` | Combined effect, not an isolated mechanism |
| Stratograph | Fixed proxy → fixed trainable | Evaluator trainability |
| Stratograph | Fixed trainable, no normalization → RMS | RMS normalization |
| Stratograph | Fixed trainable RMS → training-standard normalization | Normalization alternative |
| Stratograph | Fixed trainable, fresh weights → compatible inheritance | Inheritance policy |
| Stratograph | Fixed trainable, quality selection → diverse selection | Selection policy |
| Stratograph | Fixed trainable RMS → evolving representation | Representation evolution |

For every fixed Stratograph control, set `evolve_representation: false`, hold readout/head width/residual settings and size bounds identical, and change exactly the listed field. The separate design audit verifies the ten one-field configuration contrasts. A single policy flag can still implement several behaviors; an archive-policy result is not proof about each internal archive mechanism.

Six-seed screening is **descriptive**, with all task-level regressions and raw pairs retained. It is not a significance test with enough resolution for ten corrected contrasts. Full factorial interactions and matched-finalist inheritance tests remain separate follow-ups; this study does not falsely isolate them.

## Nomination before independent confirmation

All candidate policies and decision rules are predefined in JSON. No confirmation seed may be inspected before nomination is recorded.

For Prism, use practical screening guards: image accuracy must be within 0.25 percentage points of the legacy mean, MSE within 2% of legacy, and language perplexity within 1% of current open. For Stratograph, guard classification within 0.25 points and MSE/perplexity within 2% of the current reference. These are provisional nomination filters, not noninferiority proofs.

Among eligible candidates, rank the equal-weight direction-aware quality effect over digits, diabetes and Shakespeare against current reference. Differences below 1% use lower total measured training time as the tie-break, then smaller serialized winners, then lexical arm ID. If no candidate qualifies, retain the reference. Do not invent a new hybrid after viewing results.

Only Prism and Stratograph are nominated; Topograph open, Primordia breadth_v2 and the contender pool remain fixed. If both nominations equal reference, omit the entire duplicate selected-bundle arm from B/C/D with a receipt. Every retained combination still includes all five systems.

## C: genuine compute limits require implementation

The planned budgets are **10 and 30 measured training seconds per benchmark**, with no transfer between tasks, at most 256 proposals per run and the same run safety timeout. Report actual training seconds, updates, examples/tokens, inherited work and model sizes. A common ceiling is not proof of exactly equal consumed work or FLOPs.

The current engine contract counts fit/eval passes; `--timeout` is an invocation safety bound, and incomplete proposal-budget runs fail normal completion checks. Therefore neither a shorter timeout nor a different proposal count implements C. No existing command is presented as doing so.

Before C, implement and qualify an additive budget/termination/export contract for all five systems. Define score-availability timestamps and within-budget checkpoints. Candidates finishing after a task budget cannot supply that cutoff's winner. Distinguish expected budget exhaustion, proposal-cap saturation, missing outcomes and genuine worker failures. Preserve strict validation for historical fixed-proposal runs.

Qualification must establish usable outcome and required-floor coverage at the predeclared caps. If it cannot, stop C and issue a new protocol before inspecting scientific outcomes; do not silently increase caps or drop a baseline. Label proposal-cap-limited cases rather than claiming equal consumed work. The schema-valid fixed-proposal campaigns remain useful independently of this gated stage.

## Profiling and stopping safely

Q-core measures 128-to-256 scaling, with Topograph and Primordia as profiling priorities. Capture data preparation, compile/inheritance, training, validation, search, worker transport, serialization and checkpoint publication separately. Top-level intervals must be disjoint; document nested measurements and the unaccounted remainder. Synchronize asynchronous backend work at defined measurement boundaries.

Use paired profiled/unprofiled Q repeats to measure instrumentation overhead and confirm identical random streams, fits and winners. Do not enable intrusive profilers on confirmation runs. Baseline attempt timers are useful but do not identify every source of the observed non-training time.

Qualify graceful pause/resume **before** the next long job. A pause should finish a bounded active fit, commit it and close the invocation clock, then resume with the remaining budget. Verify that completed slots are never retrained and that no fit is charged twice. A hard-killed fit remains visible; never fabricate a clock end or erase its work. Contenders must finish a bounded slot or use a separately qualified resume contract. The prior interrupted-slot restart amendment is preserved, not generalized into silent retry permission.

## D: broader language evidence without test leakage

The pack includes original Shakespeare, 64-token Shakespeare contexts, 64-token Aesop contexts, and delayed-copy memory. These implementations exist, but the pack is still experimental and not admitted as full-fidelity local-safe.

Q-breadth must verify every engine/task, causal inputs, exact source/cache hashes, native replay, bounded runtime and contender adequacy. Merely running a tiny Transformer does not establish that it is an adequate baseline for the longer-memory task. An unavailable or inadequate baseline must block the affected claim and be resolved before that confirmation stage.

The main breadth quality panels cover the **two real-text breadth tasks**. Original Shakespeare is a bridge result; delayed-copy is a separately reported diagnostic. Synthetic-memory gains must not conceal real-text regressions.

All planned training uses training/validation data. The last 15% of real text stays protected. A separate frozen-winner test evaluator is an implementation requirement for any future protected-test claim, with no subsequent policy or checkpoint selection. It is not presently implemented or launched by this plan. Delayed-copy currently has no protected test split. Fresh seeds and another corpus establish bounded robustness evidence, not universal architecture or transfer superiority.

## Analysis and evidence

Use independent paired seeds: six for screening, twelve for each subsequent stage. Seed ranges are disjoint: Q-core 1001–1002, Q-breadth 1003–1004, A 1011–1016, B 1101–1112, C 1201–1212, D 1301–1312. The generator checks overlap against seed fields in tracked historical governance JSON; this is not a claim of global novelty in every untracked local experiment.

Keep raw scores, practical changes and costs alongside 4,096-resample paired-seed intervals. Use the 1% symmetric-effect materiality band. Predeclare and retain the six B panels, twelve C panels and six D panels in their respective Holm families, including unavailable contrasts. All task-specific rankings, nomination guards and cost comparisons remain descriptive. No automatic promotion follows from a p-value.

Remove a ceiling task from an aggregate only when every paired observation in both arms is at the known ceiling. Keep banknote as a regression sentinel and keep all raw results. Report failures, missing cells, restart costs, model size, memory, inheritance and revival/coverage diagnostics for every engine.

Current `cohort-report` differentiates engine/budget arms, not every same-engine/same-budget policy treatment. A policy-aware analysis schema or independently validated analyzer must bind full config hashes and preserve intentional intervention differences. Do not suppress normal protocol blockers or pool repeated identical controls to obtain statistical significance.

## Prepared artifacts and remaining gates

The planning generator performs no downloads, fits, scheduler changes or test access:

```sh
.venv/bin/python scripts/research/prepare_next_study.py \
  .artifacts/next-research-study-20260914-final
```

Use a fresh output path on subsequent invocations. It emits 96 validated campaign specifications and 384 native-engine configurations, plus the full 840-slot matrix grouped into 168 five-system campaigns. The remaining 72 campaigns are conditional: selected policies have not yet been nominated, or measured-budget execution is unavailable. Their `spec_file` is explicitly null, so unresolved treatments cannot accidentally execute as reference.

Preparation validates configurations and design consistency. It does **not** constitute campaign data/environment preflight, breadth qualification, timing-contract acceptance or launch authorization. Before dispatch, resolve the relevant gates, merge reviewed infrastructure, freeze the exact producer/dependencies/data and materialize the stage's immutable manifests.

## Cost envelope

This is a staged multi-day study, not a single unattended batch approval. At the full 840-run ceiling, 1,500 seconds per run gives a **350-hour run-invocation upper bound**, plus at most 8 hours 20 minutes for the separate profiling-repeat bound. Preparation, validation, replay and analysis are additional. Actual measured-compute fits can be below their maxima.

Using the last observed current-policy core means and historical Contenders durations, Q-core + A + B are roughly **26 hours before validation**. This is a planning reference, not a reliable ETA for changed policies or instrumentation. Breadth and measured-compute durations are unqualified until Q. Record stage-level forecasts and review failures/coverage before advancing.
