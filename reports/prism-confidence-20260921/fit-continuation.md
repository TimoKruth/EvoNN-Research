# Prism per-fit timeout continuation — September 22, 2026

The user requested “Fix and resume please” after the previous continuation
finished 128 attempts but failed admission because one fit reached its
120-second training cap. The other 127 attempts succeeded. The failed cell is
`frontier_v2`, language breadth at 128 fits, seed 21601; attempt 57 is an
attention model on `aesop_context64_lm`. Cumulative execution took 2,559.56
seconds, within the 19,800-second run cap.

A separate diagnostic repeated the exact saved model, initial weights, data,
seed and training policy with a larger timeout. It succeeded in 79.25 training
seconds and 768 updates. This supports a load-sensitive timeout diagnosis;
it does not establish a deterministic model failure. The diagnostic is retained
as one additional fit and is excluded from comparison observations.

Every unfinished cell now receives the same 1,800-second per-fit safety cap
and 43,200-second cumulative safety cap. These are ceilings, not target training
durations. Epoch counts and early stopping, fit counts, all eleven variants,
30 paired seeds, ordering, datasets, NumPy optimizer and inference rules remain
fixed. The producer stays at `3991748`; no engine or training code changes.

All 22 qualification and 30 main completions are retained and revalidated
under their historical identities. The failed cell restarts in a new directory.
The preceding 98-attempt cumulative timeout and this 128-attempt failed run
remain immutable, with all 226 charged attempts reported as additional cost.
Earlier validator-repair costs remain in the preceding recovery records.
Neither failure is converted into a successful observation or retried inside
its original checkpoint. The controller binds the predecessor manifest,
controller, failure and failed-run documents by checksum.

This is an amended fixed-fit, within-Prism comparison with mixed safety caps
and historical producer versions. It cannot establish equal-wall-time or
other-engine superiority. Scores did not determine this amendment. Statistical
inference remains blocked until full successful coverage and winner replay.
A further execution failure remains visible and stops the controller.

Five targeted tests passed, covering cap admission, unchanged scientific
settings, exact-slot dispatch, rejection of unexpected failure modes, duplicate
completion handling, and blocked inference on incomplete coverage. The saved
failed candidate also passed a real native MLX diagnostic. The existing frozen
producer's native pause/resume and replay checks remain applicable.

Current execution directory:
`.artifacts/prism-confidence-fit-resume-20260922/`.
The producer remains in the preceding budget continuation directory; the new
`resume.sh` uses that exact interpreter and source tree.

```sh
cat .artifacts/prism-confidence-fit-resume-20260922/study/status.json
tail -n 20 .artifacts/prism-confidence-fit-resume-20260922/run.log

# Stop after the active cell and its replay.
touch .artifacts/prism-confidence-fit-resume-20260922/study/PAUSE

# Revalidate or analyze; incomplete analysis cannot produce inference.
.artifacts/prism-confidence-fit-resume-20260922/resume.sh preflight
.artifacts/prism-confidence-fit-resume-20260922/resume.sh analyze
```

The background launcher uses launchd, Standard priority and sleep prevention.
It holds controller and campaign leases and does not automatically restart a
failed execution. Startup first revalidates the 52 inherited runs and all 33
amended campaign manifests before dispatching training.

The [launch receipt](../../governance/prism-confidence-fit-resume-20260922.json)
records the background start at 07:53 CEST. The amendment checksum is
`45c9dc6238f40893d1a7b595b9f0855371d36fe8f2e1150f4ea09242b3b5b900`.

Startup verification confirmed active native training after the complete audit,
with 3 successful new fit(s) and no failed new fits at the check. The
restarted cell is still in progress; the study is not yet complete.
