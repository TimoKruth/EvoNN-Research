# What the completed qualification tells us

The available results support useful engineering decisions and research hypotheses. They do not yet establish a generally superior engine or qualify the full study. The core matrix is complete (20/20 runs); breadth is incomplete (8/10). There are only two seeds per regime. All scores are validation-selected winners, without protected-test evaluation.

The [numerical report](report.md) contains every system, both core budgets, breadth results, named language baselines and raw seed-level winners. [analysis.json](analysis.json) retains provenance hashes, full score pairs, model sizes and recorded training costs. Reproduce with `scripts/research/analyze_qualification.py BASE FRESH_OUTPUT_DIRECTORY`.

## Engine trade-offs

**Prism has the strongest observed language results.** At core budget 256, its mean Shakespeare perplexity is 14.864, versus 16.724 for Primordia, 17.146 for Topograph and 17.327 for Stratograph. Prism beats each of them on both seeds in that regime. On 64-context breadth tasks, its means are 12.753 on Shakespeare and 10.397 on Aesop: respectively 13.6% and 17.0% below Stratograph, the next-best mean. Both seed-level comparisons favor Prism. This makes the planned Prism mechanism study worthwhile, particularly its image/regression trade-offs. It does not isolate whether attention, inheritance, archive policy or training allocation caused the result.

Prism's core-256 Shakespeare winners average about 41.8 kB serialized, versus 514.7 kB for Topograph. This is a useful artifact-size observation; serialization formats, transient memory and inference cost are separate measurements.

**Topograph benefits materially from the larger core budget.** Its mean diabetes MSE falls from 2845.3 to 2618.6 (8.0% reduction), and Shakespeare perplexity from 18.546 to 17.146 (7.5%). The regression improvement comes entirely from seed 1001; seed 1002 is unchanged. Its lowest mean regression error at budget 256 is not a per-seed sweep: Stratograph wins seed 1001 and Primordia narrowly wins seed 1002. Its digits accuracy is the best engine mean at 98.47%, while the full contender pool averages 98.61%. There is no robust image winner from two seeds.

**Primordia is a useful candidate for measured-compute testing.** At core 256, recorded training time averages 37.9 seconds across all tasks, compared with 147.8 for Prism and 269.2 for Topograph. Primordia's MSE (2680.3) and perplexity (16.724) are competitive here, while its digits accuracy (97.50%) is weaker. These are backend-specific timers under different training policies, not matched compute or proof that Primordia would win under a shared time ceiling. Its breadth quality is unknown: the two missing slots are a loader failure/dependency, not low scores.

**Stratograph's temporal behavior deserves targeted investigation.** Its delayed-copy perplexity averages 7.366, with a large seed spread (9.122 and 5.610). Topograph averages 1.699; Prism and the tiny Transformer baseline are both near 1.001. Stratograph still performs reasonably on real text (14.769/12.524 on the two breadth corpora). This discrepancy motivates tests of temporal readout, representation and training allocation; it does not by itself diagnose a specific mechanism. The synthetic memory task must remain separate from real-text quality panels.

**Contenders remain essential.** The pool has the highest mean digits accuracy at both budgets and ties everyone at 100% banknote accuracy. Its tiny Transformer solves delayed copy, so the baseline is demonstrably capable of that diagnostic. Real-text baseline strength needs closer review: at core 128, the tiny Transformer's mean Shakespeare perplexity is 37.544, worse than the unigram's 33.961. Running a Transformer successfully is not sufficient evidence of adequate tuning. Inspect its learning curves, training allocation and text-model settings before attributing the engines' large text margins to architectural superiority.

## More fits are not uniformly productive

Doubling core fits produces these changes in mean validation winners:

- Prism: +0.694 percentage points on digits, unchanged MSE, 4.15% lower perplexity; 2.10× recorded training time.
- Topograph: +0.417 points, 7.97% lower MSE, 7.55% lower perplexity; 3.68× training time.
- Stratograph: +0.417 points, 0.87% lower MSE, 3.28% lower perplexity; 2.13× training time.
- Primordia: +0.833 points, 0.55% lower MSE, 8.25% lower perplexity; 2.15× training time.
- Contenders: +0.278 points, unchanged MSE, 3.98% lower perplexity; 2.10× training time.

Banknote is at 100% for all 20 core runs. Retain it as the declared regression sentinel, but its ties offer no useful ranking signal. The results favor studying allocation and marginal returns before multiplying the fit budget everywhere. Do not treat the paired budgets as four independent seeds.

## Execution is a substantive finding

The run exposed two distinct readiness problems: the qualification launcher exhausted its supervisory timer during repeated checkpoint verification, and Primordia's owned loader lacks the breadth pack's byte-corpus and delayed-copy support. Scheduling changes recovered the former while preserving prior work; the latter remains unresolved and leaves this comparison incomplete.

Topograph's recorded checkpoint-publication time averages 131.6 seconds at 128 fits and 325.4 seconds at 256 fits, versus 73.1 and 269.2 seconds of recorded training respectively. Publication is only part of the orchestration cost: repeated full-chain checkpoint reads also caused the supervisory failures. Profile these paths before making the study much larger. Do not add nested worker profile fields together or rank engines by export elapsed time, which includes scheduler gaps and manual pauses. Profiling equivalence/reconciliation remains an open gate.

## Recommended next work

1. Resolve Primordia's two unsupported loaders in a separately qualified source change; preserve the current 28-run evidence and label any future repaired-source evidence explicitly.
2. Audit real-text contender adequacy and Stratograph's delayed-copy behavior with bounded diagnostic tests.
3. Profile and optimize checkpoint verification/publication, then establish the declared common measured-training budget. Primordia's apparent economy and Topograph's expensive scaling make this particularly informative.
4. After the relevant qualification gates pass, execute the planned mechanism screening and fresh-seed confirmation. Focus hypotheses on Prism's language/image trade-off and Stratograph's representation/temporal behavior, while retaining all four engines plus Contenders on every declared combination.

No new training is launched by this analysis. No policy is nominated from Q, no statistical promotion is issued, and the study does not advance automatically. Seeds differ from the previous 64-run engine refresh, so these results do not establish paired before/after version improvement.

## Verification performed

All 28 completion-receipt document hashes and all additional artifacts consumed by the analyzer matched. The completed runs contain 4,352 successful charged attempts, with no failed or invalid fits in those exports; this does not erase the separately retained execution/preparation failures. Winner selection agrees with the result records. The 88 recorded native winner replay checks agree with the exported metrics. An independent reconstruction using native replay values and raw contender records matched all 112 task winners. Dataset provenance matched across engines within each of the 24 benchmark/budget/seed groups. These checks do not rerun models, audit every binary export artifact, establish baseline adequacy, or establish causal/test-set generalization.
