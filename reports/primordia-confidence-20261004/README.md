# Primordia completed-study findings — October 4, 2026

All 416 comparisons and 26 qualifications completed, covering 13 presets, 16 paired seeds and two packs. This is within-Primordia validation evidence; it neither ranks other engines nor measures protected-test generalization.

## Tested standard: full_steady

`standard` is an exact policy alias for the tested `full_steady` configuration: expressive_v3 representations, steady_v3 training, progress_v3 proposals and enabled inheritance. It is a practical default choice, not an overall winner declared by the protocol. It preserves the combination that performed well across image and language tasks.

| Endpoint | Control mean | Standard mean | Paired improvement | Simultaneous 95% interval | Decision |
|---|---:|---:|---:|---:|---|
| digits_image | 97.24% | 99.67% | +2.43 pp | [+1.69, +3.17] pp | after_supported_material_gain |
| diabetes_regression | 2596.8176 | 2446.7301 | 5.97% reduction | [0.59, 11.06]% | inconclusive |
| shakespeare_byte_lm | 17.2093 | 14.6054 | 14.89% reduction | [7.31, 21.86]% | after_supported_material_gain |
| shakespeare_context64_lm | 14.7441 | 12.0829 | 17.80% reduction | [11.56, 23.60]% | after_supported_material_gain |
| aesop_context64_lm | 12.7602 | 10.1563 | 20.36% reduction | [15.45, 24.98]% | after_supported_material_gain |
| delayed_copy_lm | 15.9055 | 1.0003 | 93.71% reduction | [93.70, 93.73]% | after_supported_material_gain |

Banknote accuracy was 100% for every arm and is outside the six-endpoint inferential family.

The intervals are the frozen approximate simultaneous bootstrap intervals across 468 contrasts; decisions also require Holm-adjusted exact sign-flip p ≤ 0.05 and the predeclared materiality threshold. Loss reductions transform the paired mean log ratio, so they differ from ratios of arithmetic means. The regression contrast has Holm p ≈ 0.033 but fails the materiality/interval gate and remains inconclusive.

Standard recorded 3.74× the control's total training seconds across the 32 runs. This is descriptive: the continuation mixes producer revisions and timeout caps, and concurrent host use affects timing. It establishes no equal-wall-time efficiency claim.

## Implemented choices

- Bare fresh CLI runs use standard. Explicit configs, low-level APIs, campaign controls and historical resumes retain their prior semantics.
- All 13 historical presets remain selectable. The original experiment roster and artifacts are unchanged.
- Experimental `portfolio` and `portfolio_stable` repeatedly introduce convolution, attention and multiscale language founders, and pooled/flat spatial image founders. Family allocation depends only on task/modality, not benchmark ID or observed winners.
- Portfolio tabular proposals retain v2 representations. Each portfolio keeps its named optimizer/search settings; this is not a claim that all tabular behavior matches control.
- Exploration counters survive checkpoints; exports verify family accounting and recurring fresh-family allocation against the ledger.

Attention solved delayed copy but its natural-language improvements were inconclusive; convolution/multiscale improved natural language but did not solve delayed copy. The portfolio keeps both opportunities. It is a new hypothesis, not a measured improvement. Full versus steady/cold comparisons do not justify declaring a universal winner or disabling inheritance.

## Next comparison

Compare control, standard, portfolio and portfolio_stable on fresh paired seeds. Each new declared case must run Prism, Topograph, Stratograph, Primordia and Contenders. Existing study seeds are development evidence and must not serve as fresh confirmation. Include quality, failures, actual optimizer updates and measured training time. No new study was launched by this implementation.

## Reproduction

Run `.venv/bin/python reports/primordia-confidence-20261004/analyze.py` to regenerate this summary from the frozen report.

Source: `reports/primordia-confidence-20261004/evidence.json`

SHA-256: `fd4d7e7cd0e1c76a41944bd9dfa90d96048f037c4ee3b5e70f5098c1aff6109b`
