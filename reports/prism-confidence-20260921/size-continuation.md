# Prism parameter-size repair — September 23, 2026

The previous continuation stopped at `broad`, core budget 256, seed 21605.
It executed 256 proposals, but attempt 223 was rejected before training because
its convolution model compiled to 3,367,792 parameters, above the existing
2,000,000-parameter runtime cap. Thus 255 fits were charged and one proposal was
invalid. The export correctly rejected the missing evaluation; the validator
and accounting must not be weakened to admit it.

The user requested “Fix and Resume”. Producer `7cf5bbb` descends from frozen
`3991748` with two production files changed plus regression tests. Before a fit,
`compile_candidate` keeps an under-cap candidate exactly unchanged. An oversized
evolved candidate deterministically reduces each hidden width to three quarters
(with a minimum of four), repeating compilation until it fits. Attention and
composite candidates also reduce embedding width while retaining head divisibility
and RoPE requirements. Family, depth, kernel, training settings and random stream
are preserved. No candidate is resampled and no additional training fit is spent.
An explicit fixed architecture is never silently resized.

The proposal records the original genome, original count, effective count and
`shrink_widths_v1` policy. Parent lineage is retained; operator attribution changes
to the constraint so resized models cannot claim a function-preserving widening.
The hard 2-million cap and ordinary failed/invalid accounting remain in place.
The diagnosed model becomes 1,885,990 parameters with widths 150/160/160/160.

A separate continuation retains all 22 qualification and 141 main completions
with their existing identities and revalidates them before dispatch. It restarts
only the failed cell in a fresh directory. All original studies, exports and
failure records remain unchanged. The continuation reports 481 charged attempts
and one invalid proposal across its three failed predecessors as extra cost;
earlier validator-repair and diagnostic costs remain in preceding records.
The native diagnostic adds eight fits and is excluded from comparison results.

All unfinished cells use the same repaired producer. Fit counts, epochs, eleven
variants, 30 paired seeds, scheduled order, datasets, optimizer, 1,800-second fit
cap, 43,200-second run cap and frozen inference rules remain unchanged. Completed
cells required no constraint because every historical proposal was within cap.
Results describe this amended fixed-fit within-Prism protocol, with mixed
historical producer identities and caps. No equal-wall-time or other-engine
claim is supported. Inference stays blocked until full coverage and winner replay.

Validation: 70 Prism tests passed, including determinism, unchanged small models,
lineage and resume preservation, worst-case convolution/composite sizes, fixed
architecture rejection and native training. Six controller tests passed. An
8-fit native smoke run injected the exact rejected genome, applied the size
constraint, passed export validation, and replayed all eight winners. Production
files and regression tests pass lint.

Current execution directory:
`.artifacts/prism-confidence-size-resume-20260923/`.

```sh
cat .artifacts/prism-confidence-size-resume-20260923/study/status.json
tail -n 20 .artifacts/prism-confidence-size-resume-20260923/run.log
touch .artifacts/prism-confidence-size-resume-20260923/study/PAUSE
```

The launchd job uses Standard priority, sleep prevention, exclusive leases and
no automatic restart after failure. Startup reports inherited-run verification
progress in its log. The [launch receipt](../../governance/prism-confidence-size-resume-20260923.json)
binds the producer, controller and amendment identities.

Startup verification confirmed all inherited checks and campaign preflights
passed, with 70 successful new fits and an active native worker in the
restarted `broad` core@256 seed21605 cell. The cell and full study remain in
progress. The amendment checksum is `b0756cb4ea336fd930f8e37496f37315472649aa73bae630e3f2b04473a61339`.
