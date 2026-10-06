# Stratograph-only matched-preset study — 2026-09-21

Status: preparation authorized; training not started. The user explicitly asked
to compare only Stratograph and confirmed all eleven current presets. This is a
scoped within-engine exception to the ordinary all-engine comparison roster;
general campaign admission and historical protocols remain unchanged.

## Frozen design

All arms use native MLX on CPU, the same machine/dependencies, 12 maximum epochs,
population 4, the shared graph variant, identical per-fit/per-run limits and
matched dataset/search seeds. A clean private producer snapshot and content-bound
dataset splits prevent concurrent development from changing the experiment.

| Stage | Arms | Packs | Seeds | Fits per run | Runs | Fits |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Execution qualification | 11 | 2 | 1799 | 16 | 22 | 352 |
| Main paired study | 11 | 2 | 1701–1716 | 128 | 352 | 45,056 |
| Total | | | | | 374 | 45,408 |

Arms: `v2_reference`, `v3_control`, `attention_only`, `dilated_only`,
`stabilized_prefix`, `attention`, `dilated`, `hybrid`, `hybrid_fresh`,
`hybrid_dropout`, `evolving`. The graph/search/training choices in each preset
are explicit in the machine-readable manifest. Qualification results cannot
select/drop an arm or change the frozen main protocol.

Packs: `tier_b_core_v2` and `language_breadth_v1`. Core covers banknote, digits,
diabetes and short-context Shakespeare. Breadth covers short/context-64
Shakespeare, context-64 Aesop and delayed copy. The shared short-context task
appears in two search-pack regimes; these are distinct declared cells and are
not pooled as additional independent replicates.

The 16 independent matched seeds are the statistical replicates. Fits inside a
search run and multiple tasks are not additional independent samples. Arm order
rotates between paired seed/pack blocks. Runs execute serially to reduce direct
resource contention; changing background host load remains a limitation.

## Analysis fixed before results

Reference contrasts compare each of the ten other presets against
`v2_reference` on three panels: core, real text, and delayed copy. The complete
family therefore contains 30 two-sided tests. This compares search/training
policies; it is not a fixed-architecture causal mechanism experiment.

For each seed and task, compute the symmetric relative gain
`2 * (candidate - reference) / (abs(candidate) + abs(reference))`, reversing
the sign for MSE/perplexity. Both-zero and ceiling ties contribute zero.
Average tasks equally within each panel and then analyze the 16 paired seed
effects. Do not average raw accuracy, MSE and perplexity or change task membership
based on observed ceilings/results.

Use the existing `paired_inference` implementation: 4,096 deterministic paired
seed bootstrap resamples for pointwise 95% intervals, and a two-sided signed-rank
permutation test with up to 8,192 permutations. Correct p-values using Holm over
all 30 declared contrasts, including unavailable tests as p=1. Independent seed
effects and symmetry under the null are assumptions of the inference. Correlated
panels are retained in the same multiplicity family.

A material-gain label requires a complete study, adjusted p < 0.05 and the
pointwise lower interval endpoint above 0.01 (1% symmetric relative gain).
The intervals are not simultaneous 95% intervals. A non-significant result is
inconclusive, not evidence of equivalence. `v3_control` remains a diagnostic
control; absence of significance does not prove numerical equivalence.

Show seed-level outcomes and intervals for every preset. Report measured
training seconds and optimizer updates separately from orchestration time.
Keep memory and real-text results separate. There is no automatic unique-winner
claim between nonreference arms, engine promotion, protected-test generalization
claim or comparison to another engine. Sixteen seeds allow useful paired
inference but do not guarantee power for arbitrarily small improvements; broad
intervals remain inconclusive. Do not extend seeds after looking at significance
without a separately frozen follow-up.

## Execution and failure rules

Qualification must complete all 22 exports and saved-winner replays before any
main slot dispatches. Every main winner is also replayed. Run caps: 1,500 seconds
per engine run and 120 seconds per fit, within the existing engine limits.
Each orchestration invocation lasts at most 1,800 seconds. The launcher can invoke
successive sessions until completion; no scheduler/background service is installed.
Runtime is to be measured during qualification; the sum of caps is not an ETA.

Every declared cell must complete with its full successful fit count and verified
dataset provenance. Failed/invalid attempts, missing exports, replay errors or
source/environment drift stop progress and keep the study incomplete. Preserve
all failed evidence; do not silently replace seeds, trim arms, discard an outlier
or retry a charged failed fit. Producer repairs require a new frozen study.

The manifest records the producer commit, source hash, dependencies, machine
identity, dataset checksums, every run configuration and hypotheses. A `PAUSE`
file stops new dispatches after the current bounded run finishes. Resuming uses
the same manifest and engine journals. A retained failure requires investigation
and is not automatically retried. Existing all-engine campaigns are unaffected.

The preparation receipt will record the private producer location, manifest
digest, dataset verification, seed-audit scope, validation and exact launch command.
No training is authorized by preparation alone.
