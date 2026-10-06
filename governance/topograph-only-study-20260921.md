# Topograph-only comparison protocol — 2026-09-21

The user explicitly requested **only Topograph**, and selected **all 19 current
variants/settings, with staged screening and confirmation**. This is a scoped
exception to the repository's general all-engine roster rule. Other engines and
Contenders are excluded from this study; no external-floor or cross-engine claim
is possible. Historical comparisons remain unchanged.

## Frozen design

| Stage | Arms | Paired seeds | Fits per run | Epoch ceiling | Runs | Fits |
|---|---:|---:|---:|---:|---:|---:|
| Qualification | 19 | 1 | 16 | 2 | 38 | 608 |
| Screening | 19 | 4 | 128 | 12 | 152 | 19,456 |
| Confirmation | 3–4 | 16 fresh | 256 | 12 | 96–128 | 24,576–32,768 |

Each arm/seed executes both `tier_b_core_v2` and `language_breadth_v1`, with all
four declared tasks in each pack. Total: **286–318 runs / 44,640–52,832 fits**.
Budget is per pack/run, not per task. Use MLX native on CPU, population four,
one isolated fit worker and one study run at a time. Qualification has a five-minute
run ceiling; later runs have a 25-minute ceiling and two-minute individual-fit
ceiling. These ceilings are safeguards, not runtime forecasts. Short qualification
does not prove that every 256-fit run will finish under its ceiling; failures keep
the scientific comparison incomplete. Local free-disk reserve is checked before
runs. No new training is authorized by preparation alone.

The six previous variants are `legacy`, `mechanics`, `training`, `archive`,
`broad`, `open`. The thirteen new settings are `next`, `query`, `mixer`,
`legacy_adapters`, `full_training`, `coverage_training`, `quality_selection`,
`broad_mutation`, `cold`, `no_smoothing`, `all_decay`, `wide_cap`, and
`more_crossover`. Complete options are frozen in each campaign manifest.

Qualification seed: 32701. Screening seeds: 32711–32714. Confirmation seeds:
32801–32816. These sets are disjoint and are checked against JSON receipts in
`governance/` and `reports/`; unknown external runs are outside the audit. Within
seed/pack blocks, arm order is deterministically shuffled before outcomes exist.
No screening result is counted as confirmation evidence.

## What “with confidence” means here

Use paired independent **seeds**, not trials, models, tasks or reused pack results,
as statistical units. The primary index gives equal weight to image, regression
and real text. It consists of digits accuracy, diabetes MSE, and the mean of
Shakespeare byte-context, Shakespeare 64-context and Aesop 64-context perplexity.
For each task, gain is direction-adjusted `2*(candidate-control)/(|candidate|+|control|)`.
These are symmetric relative effects, not percentage-point accuracy differences.

Banknote remains a ceiling sentinel. Delayed-copy remains a separate memory
sentinel. Both are executed and reported, but neither enters the fixed primary
index. The duplicate Shakespeare-byte result from the breadth pack is also
reported separately, preventing accidental double weighting. The index and these
exclusions are declared before any new scores are available.

Only after every qualification and screening run has a complete verified export
and a passing saved-winner replay, nominate the arm with the largest mean primary
index relative to `open`. Exact ties use the declared arm order. If no arm has a
positive mean effect, retain `open`. Freeze the nominee and the screening-evidence
hash before preparing confirmation. Screening is descriptive; it makes no
significance or promotion claim.

Confirmation runs `legacy`, `open`, `next` and the frozen nominee, deduplicated,
on all 16 fresh seeds. The three prespecified nominee-versus-control contrasts
form one Holm correction family at alpha 0.05. A self-comparison or unavailable
test remains in that family with p=1. Report 95% paired-seed bootstrap intervals
and 98.333333% Bonferroni intervals across the three primary contrasts, using
32,768 deterministic resamples. Signed-rank permutation tests use the existing
8,192-permutation implementation and its symmetry assumption.

A **confirmed aggregate gain against a named control** requires both Holm p≤0.05
and the simultaneous interval's lower bound above the 1% materiality threshold.
This does not establish superiority on each task or against every control.
Per-task effects, all raw seed scores, model sizes, actual optimizer updates and
recorded training time remain visible. Runtime is descriptive under this fit-budget
protocol. No automatic promotion, optional stopping, post-result seed additions
or universal winner declaration is allowed. A complete study may be inconclusive;
16 seeds provide replication, not a guaranteed ability to detect small effects.

All scores are validation-selected. Protected test data stays unused. No claim
about test-set generalization, causal mechanisms, larger architectures or baseline
adequacy follows from these comparisons.

## Execution and failure handling

The reusable controller is `python -m evonn_compare.topograph_study`. Preparation
freezes source/dependencies/host, policies, split provenance and campaign checksums
without fitting. The working repository is changing in other threads, so the
actual prepared study uses a separate committed producer and its own environment.
Use the launch instructions in the preparation receipt; launching from the mutable
main workspace would correctly fail the identity checks.

Commands, from that producer:

```sh
.venv/bin/python -m evonn_compare.topograph_study preflight <study>
.venv/bin/python -m evonn_compare.topograph_study run <study> --stage qualification
.venv/bin/python -m evonn_compare.topograph_study run <study> --stage screening
.venv/bin/python -m evonn_compare.topograph_study nominate <study>
.venv/bin/python -m evonn_compare.topograph_study prepare-confirmation <study>
.venv/bin/python -m evonn_compare.topograph_study run <study> --stage confirmation
.venv/bin/python -m evonn_compare.topograph_study report <study> --stage confirmation
```

Each execution invocation is bounded to 30 minutes and may return incomplete while
leaving valid progress to resume. Repeat the same stage command until complete.
`--max-runs 1` provides a single-run invocation. `pause` requests a stop between
runs; `resume --stage <stage>` clears that marker and continues the selected stage.
No scheduler is installed during preparation. Qualification gates screening;
complete screening and an immutable nomination gate confirmation.

Failed fits, missing runs, inconsistent source/data, altered campaign manifests
and failed winner replays remain explicit blockers. Existing failed evidence is
never omitted or replaced automatically. Resolve execution issues under a separate,
recorded repair decision; a changed producer requires separately identified evidence.
