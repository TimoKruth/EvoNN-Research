# Stratograph eleven-preset results — 2026-09-30

All 374 planned runs completed: 22 qualification and 352 main runs. The final frozen controller report is complete, with no missing cells. Its export/provenance/full-epoch validation completed at 12:37 CEST. All 374 recorded export-document hashes and winner-replay receipts were independently checked, and all 30 independently recalculated effect means, intervals and adjusted p-values exactly match the final report.

## Interpretation

V3 makes a substantial improvement to language modeling. Attention and evolving meet the prespecified material-gain criterion on all three panels. Hybrid dropout has the strongest observed core and real-text means, but its memory improvement remains inconclusive. This study does not establish a unique winner among nonreference presets.

- **Balanced, lower-cost candidate: attention.** Core +3.28%, real text +15.16%, memory +26.86%; all meet the material-gain criterion. Language-pack training takes a median 1.60× the matched v2 runtime.
- **Higher-quality general candidate: evolving.** Core +4.40%, real text +20.24%, memory +26.61%; all meet the criterion. Language-pack training is approximately 1.97× v2.
- **Text-focused candidate: hybrid_dropout.** Highest observed real-text effect, +20.79%; memory CI crosses zero. Its advantage over evolving or hybrid is descriptive, not a prespecified confirmed contrast.
- **Retain dilated as a specialist/diagnostic option.** Real-text gain is +19.23% at approximately 1.60× runtime, but delayed-copy performance regresses severely.
- **Do not prefer fresh initialization from these results.** Hybrid fresh has lower observed text quality and worse memory than hybrid at essentially the same measured cost. This is an exploratory ablation observation; no confirmatory hybrid-versus-fresh test was declared.

![Paired confidence intervals by preset and panel](../.artifacts/stratograph-fit-resume-20260922/confidence-panels.png)

## Prespecified comparisons

Values below are mean symmetric relative gains versus v2, in percent, followed by pointwise 95% paired-seed bootstrap intervals. They are not ordinary percentage reductions in perplexity. Positive is better. Bold entries pass both Holm-adjusted p < 0.05 over all 30 tests and lower interval endpoint > +1%. † marks significant negative effects (Holm p < 0.05 and upper endpoint < −1%). Unmarked entries do not meet the gain criterion; non-significance does not establish equivalence.

| Preset | Core gain [95% CI] | Real-text gain [95% CI] | Memory gain [95% CI] | Language training / v2 |
| --- | --- | --- | --- | ---: |
| v2_reference | Reference | Reference | Reference | 1.00× |
| v3_control | -0.04% [-0.98, +0.86] | +0.73% [-0.14, +1.58] | -11.24% [-35.04, +12.90] | 1.00× |
| attention_only | -1.87% [-3.46, -0.40] | -4.13% [-6.25, -1.84] | **+26.86% [+9.29, +47.52]** | 1.15× |
| dilated_only | -1.45% [-2.67, -0.30] | +1.79% [+0.57, +3.04] | -153.09% [-166.90, -136.83] † | 1.36× |
| stabilized_prefix | **+2.68% [+1.91, +3.38]** | **+6.35% [+5.61, +7.14]** | -166.18% [-174.13, -155.60] † | 1.21× |
| attention | **+3.28% [+2.63, +3.90]** | **+15.16% [+13.82, +16.49]** | **+26.86% [+9.29, +47.53]** | 1.60× |
| dilated | **+4.10% [+3.41, +4.80]** | **+19.23% [+18.30, +20.13]** | -166.16% [-174.12, -155.55] † | 1.60× |
| hybrid | **+4.27% [+3.39, +5.16]** | **+20.08% [+19.28, +20.90]** | +12.85% [-11.24, +32.69] | 1.97× |
| hybrid_fresh | **+3.98% [+3.23, +4.74]** | **+18.40% [+17.49, +19.32]** | -17.80% [-51.41, +11.88] | 1.99× |
| hybrid_dropout | **+4.48% [+3.70, +5.27]** | **+20.79% [+19.85, +21.76]** | +19.31% [-5.60, +44.68] | 1.96× |
| evolving | **+4.40% [+3.77, +5.06]** | **+20.24% [+19.42, +21.07]** | **+26.61% [+8.98, +47.31]** | 1.97× |

There are 17 material-gain contrasts, three clear negative memory contrasts, and ten other contrasts. The positive tests have Holm-adjusted p = 0.00732, except evolving memory (0.00806). Hybrid and hybrid-dropout memory have adjusted p = 0.0703 and intervals spanning zero.

## What the ablations suggest

**Attention supplies a useful memory capability, but attention alone is insufficient for real text.** Attention-only reaches delayed-copy perplexity below 1.01 in all 16 seeds, while its real-text mean is −4.13% (adjusted p = 0.0610: not confirmed after multiplicity correction). The full attention preset improves real text by +15.16%. The combined representation/training changes matter; this comparison does not identify which individual change causes the benefit.

**The stabilization bundle helps text and can damage memory.** Stabilized prefix gains +6.35% on real text, but delayed-copy perplexity averages 16.08 versus 1.54 for v2. Dilated and stabilized prefix lose to v2 on memory in all 16 paired seeds. This motivates diagnosis of how the representation, readout and temporal mechanisms retain delayed information; the result alone does not identify an implementation defect.

**Hybrid memory is less reliable across seeds.** Attention-only, attention and evolving each have delayed-copy perplexity below 1.01 in 16/16 seeds. Hybrid and hybrid dropout reach that descriptive threshold in 12/16; hybrid fresh in 4/16. This threshold is an exploratory reliability summary, not a preregistered statistical test. The worst observed perplexities are 1.0054 for attention, 1.0087 for evolving, 4.31 for hybrid, 3.54 for hybrid dropout and 15.51 for hybrid fresh.

**Most of the core-panel improvement comes from Shakespeare.** Banknote is exactly 100% for every arm/seed; digits is approximately 97.0–97.3%, and diabetes MSE remains approximately 2519–2600 across arm means. Core gains should not be described as broad improvements to classification and regression. Ceiling ties retain their declared panel weight.

**The v3 control is reassuring on text/core but is not an equivalence certificate.** No panel differs significantly from v2, but its memory interval is wide (−35.04% to +12.90%). Numerical equivalence of a fixed model does not imply identical stochastic search trajectories.

## Raw language outcomes

Arithmetic means of the selected validation-winner perplexities over 16 seeds; lower is better. Short Shakespeare here uses the language-breadth search pack, not the separate core-pack run.

| Preset | Shakespeare short | Shakespeare context 64 | Aesop context 64 | Delayed copy |
| --- | ---: | ---: | ---: | ---: |
| v2_reference | 17.8889 | 14.4886 | 12.8402 | 1.5424 |
| v3_control | 17.5109 | 14.5068 | 12.8194 | 1.8581 |
| attention_only | 19.8445 | 14.6302 | 13.1169 | 1.0006 |
| dilated_only | 18.6939 | 13.9776 | 12.0825 | 13.6388 |
| stabilized_prefix | 15.9491 | 14.0075 | 12.3019 | 16.0806 |
| attention | 15.6344 | 12.6561 | 10.6919 | 1.0004 |
| dilated | 14.9615 | 12.2981 | 10.1356 | 16.0806 |
| hybrid | 14.8908 | 12.1806 | 10.0177 | 1.3537 |
| hybrid_fresh | 15.2162 | 12.2913 | 10.2215 | 2.8516 |
| hybrid_dropout | 14.6404 | 12.1037 | 10.0407 | 1.1638 |
| evolving | 14.7890 | 12.1847 | 10.0328 | 1.0032 |

For example, evolving lowers mean language-pack Shakespeare perplexity from 17.89 to 14.79, context-64 Shakespeare from 14.49 to 12.18, and Aesop from 12.84 to 10.03. These are approximately 17%, 16% and 22% reductions in the respective means, rather than the symmetric panel-effect percentages.

## Compute and completion accounting

All presets received 128 fits per main pack/seed and 12 epochs per fit. Each preset accumulated 1,529,856 optimizer updates across its 32 main runs. Equal updates/fits do not imply equal compute: the models have different per-update costs. The main runs total 79.93 measured training hours; orchestration time and manual pauses are not included.

| Preset | Main training hours | Optimizer updates | Median core training seconds | Median language training seconds |
| --- | ---: | ---: | ---: | ---: |
| v2_reference | 4.72 | 1,529,856 | 62.8 | 987.7 |
| v3_control | 4.70 | 1,529,856 | 63.3 | 990.6 |
| attention_only | 5.47 | 1,529,856 | 72.8 | 1141.6 |
| dilated_only | 6.36 | 1,529,856 | 74.8 | 1367.8 |
| stabilized_prefix | 5.81 | 1,529,856 | 89.9 | 1215.0 |
| attention | 7.79 | 1,529,856 | 101.5 | 1608.0 |
| dilated | 7.66 | 1,529,856 | 101.6 | 1656.7 |
| hybrid | 9.23 | 1,529,856 | 121.0 | 1953.2 |
| hybrid_fresh | 9.33 | 1,529,856 | 120.6 | 1967.1 |
| hybrid_dropout | 9.41 | 1,529,856 | 115.2 | 2017.6 |
| evolving | 9.44 | 1,529,856 | 118.4 | 2073.8 |

The completed study contains 45,408 successful planned fits. Four historical failed runs remain preserved and account for another 490 charged attempts (45,898 total study plus failed-run attempts; separate repair diagnostics are excluded). Source and timeout amendments are recorded in the continuation manifests. The active continuation has no unresolved failures.

## Confidence and limits

- The independent replication unit is one of 16 paired seeds, not one of the 45,408 fits or an individual task. The frozen method uses 4,096 deterministic bootstrap samples, signed-rank permutation tests and Holm correction across all 30 reference contrasts.
- Confidence intervals are pointwise, not simultaneous; the material-gain label combines them with the multiplicity-adjusted test. No post-hoc nonreference comparisons are presented as confirmatory.
- These are validation-selected search winners. Protected test data were not evaluated. Generalization to new corpora or larger budgets is not established.
- Numerical recovery and time-cap amendments produced mixed frozen source identities and safety caps. Full successful epoch budgets and original receipts are retained, but this is not one unamended producer experiment or an equal-wall-time comparison. Runtime also reflects changing host load.
- This explicitly requested study compares Stratograph presets only. It does not establish superiority over Prism, Topograph, Primordia or Contenders.

## Recommended next decisions

Keep attention as the economical balanced candidate, evolving as the higher-compute broad candidate, and hybrid dropout as the text-focused candidate. Avoid a universal switch to pure dilation. Preserve the switches and current defaults until a promotion is explicitly chosen.

Next research priorities: (1) investigate delayed-copy failures with fixed-architecture controlled probes; (2) separate the stabilization bundle into narrower ablations; (3) test inheritance and dropout with frozen direct contrasts; (4) confirm the shortlisted policies on protected/fresh data and matched wall time. Any new engine comparison must include all four engines plus Contenders under the repository rule, unless explicitly scoped otherwise by the user. These are recommendations; no new runs have been launched.

## Evidence

- [Frozen study protocol](stratograph-only-study-20260921.md)
- [Final frozen-controller analysis](../.artifacts/stratograph-fit-resume-20260922/study/analysis.json)
- [Independent cross-check, all seed effects, raw seed scores and runtime summaries](../.artifacts/stratograph-fit-resume-20260922/receipt-analysis.json)
- [Fit-time amendment](stratograph-fit-resume-20260922.md)
- [Numerical recovery amendment](stratograph-stability-resume-20260922.md)
