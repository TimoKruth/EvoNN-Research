# Qualification results — 16 September 2026

**Descriptive evidence only.** 28/30 runs complete; two Primordia breadth slots remain blocked. This is two seeds per regime, not the planned mechanism or confirmation study. No engine promotion or later-stage acceptance follows.

Inputs checked: 4,352 successful charged fits, 88 recorded native winner replay checks, and 24 within-case dataset groups. All consumed document/artifact hashes matched. This analysis does not rerun training or independently replay models.

Core coverage is complete: five systems × two budgets × two seeds = 20 runs. Breadth coverage is 8/10. Budgets count fits across the four tasks, not per task. Means below are arithmetic means of each seed’s validation-selected winner; they are not held-out test scores.

## Core at 128 fits

| System | Banknote accuracy ↑ | Digits accuracy ↑ | Diabetes MSE ↓ | Shakespeare perplexity ↓ |
| --- | ---: | ---: | ---: | ---: |
| Prism | 100.00% | 96.94% | 2725.9 | 15.507 |
| Topograph | 100.00% | 98.06% | 2845.3 | 18.546 |
| Stratograph | 100.00% | 97.50% | 2708.3 | 17.914 |
| Primordia | 100.00% | 96.67% | 2695.2 | 18.229 |
| Contenders | 100.00% | 98.33% | 2847.3 | 33.961 |

## Core at 256 fits

| System | Banknote accuracy ↑ | Digits accuracy ↑ | Diabetes MSE ↓ | Shakespeare perplexity ↓ |
| --- | ---: | ---: | ---: | ---: |
| Prism | 100.00% | 97.64% | 2725.9 | 14.864 |
| Topograph | 100.00% | 98.47% | 2618.6 | 17.146 |
| Stratograph | 100.00% | 97.92% | 2684.8 | 17.327 |
| Primordia | 100.00% | 97.50% | 2680.3 | 16.724 |
| Contenders | 100.00% | 98.61% | 2847.3 | 32.610 |

## Breadth at 64 fits

All entries are perplexity (lower is better). Shakespeare byte is a bridge task; delayed copy is a separate synthetic diagnostic. Do not average them together to claim language superiority.

| System | Shakespeare context 64 | Aesop context 64 | Original Shakespeare | Delayed copy |
| --- | ---: | ---: | ---: | ---: |
| Prism | 12.7528 | 10.3968 | 15.2257 | 1.0009 |
| Topograph | 15.4394 | 12.8219 | 19.3834 | 1.6987 |
| Stratograph | 14.7685 | 12.5238 | 16.9039 | 7.3659 |
| Primordia | Blocked | Blocked | Blocked | Blocked |
| Contenders | 27.8260 | 20.0550 | 33.2905 | 1.0009 |

## Paired budget scaling: 128 → 256

Percent reductions are ratios of the two-seed means, not means of seed-level percentages. Raw pairs are retained in analysis.json. Banknote stays at 100% for every system/seed/budget.

| System | Digits gain (percentage points) | MSE reduction | Perplexity reduction | Recorded training-time multiplier |
| --- | ---: | ---: | ---: | ---: |
| Prism | 0.694 | 0.00% | 4.15% | 2.10× |
| Topograph | 0.417 | 7.97% | 7.55% | 3.68× |
| Stratograph | 0.417 | 0.87% | 3.28% | 2.13× |
| Primordia | 0.833 | 0.55% | 8.25% | 2.15× |
| Contenders | 0.278 | 0.00% | 3.98% | 2.10× |

## Recorded training costs

Sum of per-attempt train_seconds across all four tasks, averaged over the two seeds. These are backend-specific recorded timers, not matched FLOPs or an audited common-compute budget. They exclude much orchestration/checkpoint work. Export elapsed time spans scheduler gaps/manual pauses and is unsuitable for throughput ranking.

| System | Core 128 (s) | Core 256 (s) | Breadth 64 (s) |
| --- | ---: | ---: | ---: |
| Prism | 70.3 | 147.8 | 213.6 |
| Topograph | 73.1 | 269.2 | 84.1 |
| Stratograph | 66.2 | 141.3 | 445.4 |
| Primordia | 17.7 | 37.9 | Blocked |
| Contenders | 82.0 | 172.3 | 519.8 |

## Named language baselines

These panels separate the best frozen contender pool from named baselines. Successfully executing a baseline does not establish adequate tuning or matching training effort.

| Stage / budget | Task | Family | Mean best validation perplexity |
| --- | --- | --- | ---: |
| Q-breadth / 64 | aesop_context64_lm | bigram_lm | 25.7127 |
| Q-breadth / 64 | aesop_context64_lm | transformer_lm_tiny | 20.0550 |
| Q-breadth / 64 | aesop_context64_lm | trigram_lm | 67.2596 |
| Q-breadth / 64 | aesop_context64_lm | unigram_lm | 26.0394 |
| Q-breadth / 64 | delayed_copy_lm | bigram_lm | 16.7195 |
| Q-breadth / 64 | delayed_copy_lm | transformer_lm_tiny | 1.0009 |
| Q-breadth / 64 | delayed_copy_lm | trigram_lm | 17.5076 |
| Q-breadth / 64 | delayed_copy_lm | unigram_lm | 16.0703 |
| Q-breadth / 64 | shakespeare_byte_lm | bigram_lm | 56.0582 |
| Q-breadth / 64 | shakespeare_byte_lm | transformer_lm_tiny | 36.4906 |
| Q-breadth / 64 | shakespeare_byte_lm | trigram_lm | 131.9671 |
| Q-breadth / 64 | shakespeare_byte_lm | unigram_lm | 33.2905 |
| Q-breadth / 64 | shakespeare_context64_lm | bigram_lm | 32.7681 |
| Q-breadth / 64 | shakespeare_context64_lm | transformer_lm_tiny | 27.8260 |
| Q-breadth / 64 | shakespeare_context64_lm | trigram_lm | 84.4461 |
| Q-breadth / 64 | shakespeare_context64_lm | unigram_lm | 30.5543 |
| Q-core / 128 | shakespeare_byte_lm | bigram_lm | 56.5965 |
| Q-core / 128 | shakespeare_byte_lm | transformer_lm_tiny | 37.5442 |
| Q-core / 128 | shakespeare_byte_lm | trigram_lm | 132.9746 |
| Q-core / 128 | shakespeare_byte_lm | unigram_lm | 33.9611 |
| Q-core / 256 | shakespeare_byte_lm | bigram_lm | 56.5965 |
| Q-core / 256 | shakespeare_byte_lm | transformer_lm_tiny | 34.0735 |
| Q-core / 256 | shakespeare_byte_lm | trigram_lm | 132.9746 |
| Q-core / 256 | shakespeare_byte_lm | unigram_lm | 33.9611 |

## Raw paired winners

| Stage | Budget | Seed | System | Task | Score | Winner bytes |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| Q-breadth | 64 | 1003 | contenders | aesop_context64_lm | 20.392534 | 429876 |
| Q-breadth | 64 | 1003 | contenders | delayed_copy_lm | 1.0009725 | 306011 |
| Q-breadth | 64 | 1003 | contenders | shakespeare_byte_lm | 33.295315 | 413 |
| Q-breadth | 64 | 1003 | contenders | shakespeare_context64_lm | 26.092707 | 429874 |
| Q-breadth | 64 | 1003 | prism | aesop_context64_lm | 10.238037 | 43416 |
| Q-breadth | 64 | 1003 | prism | delayed_copy_lm | 1.0016664 | 14560 |
| Q-breadth | 64 | 1003 | prism | shakespeare_byte_lm | 15.618454 | 43416 |
| Q-breadth | 64 | 1003 | prism | shakespeare_context64_lm | 12.627913 | 43416 |
| Q-breadth | 64 | 1003 | stratograph | aesop_context64_lm | 12.470609 | 47480 |
| Q-breadth | 64 | 1003 | stratograph | delayed_copy_lm | 9.1223457 | 21632 |
| Q-breadth | 64 | 1003 | stratograph | shakespeare_byte_lm | 16.702465 | 57976 |
| Q-breadth | 64 | 1003 | stratograph | shakespeare_context64_lm | 14.921223 | 47480 |
| Q-breadth | 64 | 1003 | topograph | aesop_context64_lm | 12.759923 | 536676 |
| Q-breadth | 64 | 1003 | topograph | delayed_copy_lm | 1.7305205 | 138570 |
| Q-breadth | 64 | 1003 | topograph | shakespeare_byte_lm | 19.347478 | 42536 |
| Q-breadth | 64 | 1003 | topograph | shakespeare_context64_lm | 14.887305 | 55872 |
| Q-breadth | 64 | 1004 | contenders | aesop_context64_lm | 19.717539 | 429876 |
| Q-breadth | 64 | 1004 | contenders | delayed_copy_lm | 1.0008678 | 306009 |
| Q-breadth | 64 | 1004 | contenders | shakespeare_byte_lm | 33.285741 | 405 |
| Q-breadth | 64 | 1004 | contenders | shakespeare_context64_lm | 29.559319 | 429874 |
| Q-breadth | 64 | 1004 | prism | aesop_context64_lm | 10.555615 | 43416 |
| Q-breadth | 64 | 1004 | prism | delayed_copy_lm | 1.0001125 | 13472 |
| Q-breadth | 64 | 1004 | prism | shakespeare_byte_lm | 14.832886 | 43416 |
| Q-breadth | 64 | 1004 | prism | shakespeare_context64_lm | 12.877777 | 43416 |
| Q-breadth | 64 | 1004 | stratograph | aesop_context64_lm | 12.5769 | 47480 |
| Q-breadth | 64 | 1004 | stratograph | delayed_copy_lm | 5.6095272 | 15320 |
| Q-breadth | 64 | 1004 | stratograph | shakespeare_byte_lm | 17.105251 | 47480 |
| Q-breadth | 64 | 1004 | stratograph | shakespeare_context64_lm | 14.615797 | 79960 |
| Q-breadth | 64 | 1004 | topograph | aesop_context64_lm | 12.883922 | 323308 |
| Q-breadth | 64 | 1004 | topograph | delayed_copy_lm | 1.6668166 | 184816 |
| Q-breadth | 64 | 1004 | topograph | shakespeare_byte_lm | 19.419229 | 53336 |
| Q-breadth | 64 | 1004 | topograph | shakespeare_context64_lm | 15.991423 | 48812 |
| Q-core | 128 | 1001 | contenders | banknote_classification | 1 | 186798 |
| Q-core | 128 | 1001 | contenders | diabetes_regression | 3038.6821 | 1111 |
| Q-core | 128 | 1001 | contenders | digits_image | 0.98888889 | 610114 |
| Q-core | 128 | 1001 | contenders | shakespeare_byte_lm | 34.545667 | 409 |
| Q-core | 128 | 1001 | primordia | banknote_classification | 1 | 2218 |
| Q-core | 128 | 1001 | primordia | diabetes_regression | 2992.9128 | 2166 |
| Q-core | 128 | 1001 | primordia | digits_image | 0.96388889 | 4050 |
| Q-core | 128 | 1001 | primordia | shakespeare_byte_lm | 20.433728 | 10802 |
| Q-core | 128 | 1001 | prism | banknote_classification | 1 | 3282 |
| Q-core | 128 | 1001 | prism | diabetes_regression | 3018.9759 | 1778 |
| Q-core | 128 | 1001 | prism | digits_image | 0.96944444 | 5846 |
| Q-core | 128 | 1001 | prism | shakespeare_byte_lm | 16.08485 | 40148 |
| Q-core | 128 | 1001 | stratograph | banknote_classification | 1 | 6878 |
| Q-core | 128 | 1001 | stratograph | diabetes_regression | 2824.2327 | 11196 |
| Q-core | 128 | 1001 | stratograph | digits_image | 0.98611111 | 12224 |
| Q-core | 128 | 1001 | stratograph | shakespeare_byte_lm | 18.750596 | 47480 |
| Q-core | 128 | 1001 | topograph | banknote_classification | 1 | 14374 |
| Q-core | 128 | 1001 | topograph | diabetes_regression | 3290.8864 | 36800 |
| Q-core | 128 | 1001 | topograph | digits_image | 0.98611111 | 28490 |
| Q-core | 128 | 1001 | topograph | shakespeare_byte_lm | 20.05506 | 61276 |
| Q-core | 128 | 1002 | contenders | banknote_classification | 1 | 2953215 |
| Q-core | 128 | 1002 | contenders | diabetes_regression | 2655.998 | 12909312 |
| Q-core | 128 | 1002 | contenders | digits_image | 0.97777778 | 610114 |
| Q-core | 128 | 1002 | contenders | shakespeare_byte_lm | 33.376435 | 413 |
| Q-core | 128 | 1002 | primordia | banknote_classification | 1 | 1690 |
| Q-core | 128 | 1002 | primordia | diabetes_regression | 2397.5015 | 2414 |
| Q-core | 128 | 1002 | primordia | digits_image | 0.96944444 | 29640 |
| Q-core | 128 | 1002 | primordia | shakespeare_byte_lm | 16.023684 | 23474 |
| Q-core | 128 | 1002 | prism | banknote_classification | 1 | 4878 |
| Q-core | 128 | 1002 | prism | diabetes_regression | 2432.9049 | 2162 |
| Q-core | 128 | 1002 | prism | digits_image | 0.96944444 | 10646 |
| Q-core | 128 | 1002 | prism | shakespeare_byte_lm | 14.929863 | 43416 |
| Q-core | 128 | 1002 | stratograph | banknote_classification | 1 | 8606 |
| Q-core | 128 | 1002 | stratograph | diabetes_regression | 2592.4141 | 38164 |
| Q-core | 128 | 1002 | stratograph | digits_image | 0.96388889 | 12318 |
| Q-core | 128 | 1002 | stratograph | shakespeare_byte_lm | 17.077513 | 47480 |
| Q-core | 128 | 1002 | topograph | banknote_classification | 1 | 4108 |
| Q-core | 128 | 1002 | topograph | diabetes_regression | 2399.7178 | 1774 |
| Q-core | 128 | 1002 | topograph | digits_image | 0.975 | 31454 |
| Q-core | 128 | 1002 | topograph | shakespeare_byte_lm | 17.037045 | 156676 |
| Q-core | 256 | 1001 | contenders | banknote_classification | 1 | 186798 |
| Q-core | 256 | 1001 | contenders | diabetes_regression | 3038.6821 | 1111 |
| Q-core | 256 | 1001 | contenders | digits_image | 0.99444444 | 610116 |
| Q-core | 256 | 1001 | contenders | shakespeare_byte_lm | 34.545667 | 409 |
| Q-core | 256 | 1001 | primordia | banknote_classification | 1 | 2218 |
| Q-core | 256 | 1001 | primordia | diabetes_regression | 2963.1829 | 2166 |
| Q-core | 256 | 1001 | primordia | digits_image | 0.975 | 20718 |
| Q-core | 256 | 1001 | primordia | shakespeare_byte_lm | 17.425214 | 74718 |
| Q-core | 256 | 1001 | prism | banknote_classification | 1 | 3282 |
| Q-core | 256 | 1001 | prism | diabetes_regression | 3018.9759 | 1778 |
| Q-core | 256 | 1001 | prism | digits_image | 0.98055556 | 26546 |
| Q-core | 256 | 1001 | prism | shakespeare_byte_lm | 16.08485 | 40148 |
| Q-core | 256 | 1001 | stratograph | banknote_classification | 1 | 6878 |
| Q-core | 256 | 1001 | stratograph | diabetes_regression | 2777.1722 | 17246 |
| Q-core | 256 | 1001 | stratograph | digits_image | 0.98611111 | 12224 |
| Q-core | 256 | 1001 | stratograph | shakespeare_byte_lm | 18.750596 | 47480 |
| Q-core | 256 | 1001 | topograph | banknote_classification | 1 | 14374 |
| Q-core | 256 | 1001 | topograph | diabetes_regression | 2837.3856 | 36800 |
| Q-core | 256 | 1001 | topograph | digits_image | 0.98611111 | 28490 |
| Q-core | 256 | 1001 | topograph | shakespeare_byte_lm | 17.698951 | 779646 |
| Q-core | 256 | 1002 | contenders | banknote_classification | 1 | 2953215 |
| Q-core | 256 | 1002 | contenders | diabetes_regression | 2655.998 | 12909312 |
| Q-core | 256 | 1002 | contenders | digits_image | 0.97777778 | 610114 |
| Q-core | 256 | 1002 | contenders | shakespeare_byte_lm | 30.673986 | 417586 |
| Q-core | 256 | 1002 | primordia | banknote_classification | 1 | 1690 |
| Q-core | 256 | 1002 | primordia | diabetes_regression | 2397.5015 | 2414 |
| Q-core | 256 | 1002 | primordia | digits_image | 0.975 | 29640 |
| Q-core | 256 | 1002 | primordia | shakespeare_byte_lm | 16.023684 | 23474 |
| Q-core | 256 | 1002 | prism | banknote_classification | 1 | 4878 |
| Q-core | 256 | 1002 | prism | diabetes_regression | 2432.9049 | 2162 |
| Q-core | 256 | 1002 | prism | digits_image | 0.97222222 | 10646 |
| Q-core | 256 | 1002 | prism | shakespeare_byte_lm | 13.643222 | 43416 |
| Q-core | 256 | 1002 | stratograph | banknote_classification | 1 | 8606 |
| Q-core | 256 | 1002 | stratograph | diabetes_regression | 2592.4141 | 38164 |
| Q-core | 256 | 1002 | stratograph | digits_image | 0.97222222 | 12318 |
| Q-core | 256 | 1002 | stratograph | shakespeare_byte_lm | 15.903764 | 94688 |
| Q-core | 256 | 1002 | topograph | banknote_classification | 1 | 4108 |
| Q-core | 256 | 1002 | topograph | diabetes_regression | 2399.7178 | 1774 |
| Q-core | 256 | 1002 | topograph | digits_image | 0.98333333 | 62452 |
| Q-core | 256 | 1002 | topograph | shakespeare_byte_lm | 16.593538 | 249766 |

## Scope and integrity limits

- Primordia seed 1003 failed during Aesop preparation before fits; seed 1004 was explicitly deferred for the same unsupported loader. Missing evidence is not a poor performance score.
- Two seeds give a pilot estimate only. Budgets and benchmarks are not extra independent seed replicates. No significance tests or confidence intervals are used for promotion.
- Validation-selected winners may overstate generalization. Protected text test data was not evaluated; delayed copy has no protected test split in this protocol.
- No policy treatments or mechanism ablations were run. The data cannot establish which component caused a gain.
- Seeds differ from the previous 64-run refresh, and Topograph’s producer includes the FP16 repair. Historical score differences are not paired version effects.
- Chunking, recovery, scheduler versions and manual pauses affect wall time. Profiling equivalence and disjoint timing reconciliation remain unaccepted.
- The report retains all five systems and the two missing slots. It does not mark qualification complete or authorize stages A/B/C/D.
