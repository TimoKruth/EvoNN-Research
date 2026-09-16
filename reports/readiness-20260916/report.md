# Research readiness audit — 2026-09-16

Primordia's owned loader now supports the pinned Aesop byte corpus, its declared
byte range and generated delayed-copy data. Shared/owned arrays and provenance
match exactly in all 12 real-data checks (four tasks × seeds 42, 1003, 1004).
The 32 passing Primordia and breadth integration tests include 13 new loader
checks covering parity, malformed ranges and corrupt cache/source rejection.

The original qualification stays **incomplete at 28/30**. Its frozen producer
and results have not changed. Corrected-source contract checks are separate
implementation evidence; neither their tiny budget nor the loader fix replaces
missing historical results or establishes baseline adequacy.

The separate runtime contracts completed **15/15 runs, 240/240 fits and 48/48
native saved-winner replays**: all five systems on core before/after the repair,
and all five on the repaired breadth pack, at budget 16 and seed 1411 with two
native epochs. Every core outcome score is identical before/after. The breadth
check uses the minimum contender floor, so it does not qualify the enhanced
Transformer baseline. The registry before/after decision remains **needs more
seeds**, with claim scope `contract_validation`.

## What the retained baselines show

This audit performs **zero fits and no protected-test evaluation**. It loads the
existing best validation attempt of each language baseline family in each of
six completed Contenders runs, checks model and data hashes, and reproduces
the recorded validation perplexity before evaluating training perplexity.
The table reports means over the two existing seeds in each cohort. These are
selected final models, not independent confirmation or training curves.

| Cohort | Task | Baseline | Training perplexity | Validation perplexity |
| --- | --- | --- | ---: | ---: |
| Q-breadth@64 | aesop_context64_lm | bigram_lm | 23.295 | 25.713 |
| Q-breadth@64 | aesop_context64_lm | transformer_lm_tiny | 1.896 | 20.055 |
| Q-breadth@64 | aesop_context64_lm | trigram_lm | 47.206 | 67.260 |
| Q-breadth@64 | aesop_context64_lm | unigram_lm | 25.163 | 26.039 |
| Q-breadth@64 | delayed_copy_lm | bigram_lm | 14.866 | 16.720 |
| Q-breadth@64 | delayed_copy_lm | transformer_lm_tiny | 1.001 | 1.001 |
| Q-breadth@64 | delayed_copy_lm | trigram_lm | 10.078 | 17.508 |
| Q-breadth@64 | delayed_copy_lm | unigram_lm | 15.907 | 16.070 |
| Q-breadth@64 | shakespeare_byte_lm | bigram_lm | 44.010 | 56.058 |
| Q-breadth@64 | shakespeare_byte_lm | transformer_lm_tiny | 1.434 | 36.491 |
| Q-breadth@64 | shakespeare_byte_lm | trigram_lm | 83.230 | 131.967 |
| Q-breadth@64 | shakespeare_byte_lm | unigram_lm | 31.060 | 33.291 |
| Q-breadth@64 | shakespeare_context64_lm | bigram_lm | 27.612 | 32.768 |
| Q-breadth@64 | shakespeare_context64_lm | transformer_lm_tiny | 2.071 | 27.826 |
| Q-breadth@64 | shakespeare_context64_lm | trigram_lm | 57.960 | 84.446 |
| Q-breadth@64 | shakespeare_context64_lm | unigram_lm | 28.726 | 30.554 |
| Q-core@128 | shakespeare_byte_lm | bigram_lm | 42.390 | 56.597 |
| Q-core@128 | shakespeare_byte_lm | transformer_lm_tiny | 1.531 | 37.544 |
| Q-core@128 | shakespeare_byte_lm | trigram_lm | 82.901 | 132.975 |
| Q-core@128 | shakespeare_byte_lm | unigram_lm | 31.355 | 33.961 |
| Q-core@256 | shakespeare_byte_lm | bigram_lm | 42.390 | 56.597 |
| Q-core@256 | shakespeare_byte_lm | transformer_lm_tiny | 1.447 | 34.073 |
| Q-core@256 | shakespeare_byte_lm | trigram_lm | 82.901 | 132.975 |
| Q-core@256 | shakespeare_byte_lm | unigram_lm | 31.355 | 33.961 |

The Transformers reach training perplexity roughly 1.4–2.1 on real text but
validation perplexity roughly 20–37. This large generalization gap is consistent
with overfitting. More epochs alone are not an evidence-based remedy. Their
current policy uses 20 fixed epochs, batch size 32 and learning rate 0.001;
it does not choose an earlier validation checkpoint. Native trainers can select
their best validation epoch. Both use the last-position target on these tasks,
so a token-target objective mismatch is not established by this audit.
The retained final models cannot tell us which earlier epoch was best.

Higher-order n-grams often trail the unigram even on training data. The current
add-one smoothing over a 256-byte vocabulary and sparse contexts are plausible
contributors. The audit records unseen validation contexts per seed, but does
not prove causality or select a better smoothing value. Delayed-copy Transformer
perplexity near 1 is useful diagnostic evidence, not proof that real-text
baseline adequacy is closed.

## Checkpoint replay bottleneck

One instrumented read of Topograph's existing 256-attempt checkpoint chain took
**61.404 seconds** and examined 327,571,983 bytes across 258 checkpoint files.
All input bytes were unchanged; no fit ran. JSON encoding consumed **46.197
seconds self time (75.2%)**. JSON decoding consumed 6.050 seconds. Inclusive
state-digest time was 48.147 seconds and overlaps encoding; do not add these
inclusive timings together. The loader replays the full chain and canonicalizes
the growing logical state at each record to verify integrity.

This is a single cProfile measurement, not an uninstrumented production timing
or a measured speedup. It identifies serialization/digest reconstruction as the
first optimization target. A future versioned checkpoint format must preserve
state, budget charges, corruption detection and process-death recovery. Simply
skipping historical verification would weaken the evidence contract.

## What remains before the larger study

The [follow-up plan](../../governance/readiness-follow-up-20260916.json) separates
runtime repair, baseline adequacy and checkpoint optimization. Existing mechanism
and fresh-seed stages remain gated by their original qualification and analysis
requirements. No large study or protected-test evaluation starts from this audit.
Source hashes and the unchanged historical status are recorded in the
[readiness receipt](../../governance/research-readiness-20260916.json).
