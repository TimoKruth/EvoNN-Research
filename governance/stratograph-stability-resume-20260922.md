# Stratograph backward-overflow repair and continuation — 2026-09-22

The user requested “Fix and resume please” after the comparison stopped with
87 verified runs. The failed cell was `attention_only`, language breadth, seed
1703: all 128 attempts were charged, but attempt 101 on Aesop context-64 returned
“nonfinite loss or gradient”. The original failed run and every earlier study
remain immutable evidence.

## Diagnosis and repair

The exact saved genome, inherited weights, dataset and model seed reproduce the
failure at update 67. Forward loss remains finite while float32 intermediate
gradients overflow before the existing global norm clipping. The compiled graph
has six successive temporal cells and evolved learning rate 0.03609812832914622.
The model's architecture and learning rate are retained.

A separate clean producer descends from the preceding budget-resume producer.
Its reviewed source diff changes only `training.py` and `tensors.py`. A finite
ordinary gradient is returned unchanged. If forward loss is finite but gradients
are nonfinite, the same batch, parameters and deterministic dropout seed receive
one host NumPy float64 backward evaluation. Gradients are clipped using the
existing global norm and converted to float32 before the original AdamW update.
No batch is skipped and no additional optimizer update is performed. The existing
fit deadline bounds recovery; genuinely nonfinite forward loss or failed recovery
still stops the fit.

During that recovery only, GELU bounds its tanh argument beyond the saturated
region to avoid an overflowing cubic and undefined zero-times-infinity backward
arithmetic. The ordinary backend, tensor dtype and activation path are restored
in a `finally` block. Forward inference and winner replay remain on the configured
backend. Each new fit explicitly reports `gradient_recovery`, including recovered
batch count, host float64 backend and float32 optimizer dtype. The recovery is a
numerical implementation change, not an architecture or learning-rate ablation.

The saved failing fit completed all 12 allocated epochs and 768 updates with this
repair, recovering 232 batches in approximately 66 seconds during instrumentation,
within its unchanged 120-second fit cap. A separate isolated-worker verification
and the engine regression suite are recorded with the launch evidence. Diagnostic
trials are kept under the repair directory and are not study observations.

## Evidence and comparison scope

The same user-authorized eleven-preset comparison continues. Its 87 successful
runs retain their original exports, full-epoch validation, source identities and
winner replay receipts. Ordinary finite-gradient arithmetic is unchanged, which
supports reusing those completed runs. Their producer versions remain disclosed;
no rewritten source identity or retrospective relabeling is permitted.

The interrupted cell restarts from scratch with the same seed in a new directory.
Earlier failed runs charged 127 and 107 attempts; the numerical failure charged
128, totaling 362 separately retained attempts. The planned study still contains
374 runs and 45,408 fits; successful completion without additional failures would
therefore represent 45,770 study and retained failed-run attempts. Diagnostic and
regression work is recorded separately from this study budget.

All eleven presets, 16 matched main seeds, benchmark packs, 128-fit main budgets,
12 epochs, 120-second fit deadlines, 19,800-second unfinished-run allowance, order,
30 reference contrasts, pointwise confidence intervals and Holm correction remain
unchanged. This supports within-Stratograph conclusions only. The final analysis
must disclose the numerical-recovery amendment, mixed producers and safety caps,
and all historical failure costs. No equal-wall-time claim is supported.

## Operation

The new producer diff, external controller, ancestry and manifest are content-bound.
Exclusive leases cover all four study directories; worker processes inherit those
leases. `PAUSE` in any ancestor or current study stops new dispatch after the
current run. Further failures stop execution and are not automatically retried.
All declared cells and replay receipts remain required for confidence conclusions.

```sh
.artifacts/stratograph-stability-resume-20260922/resume.sh preflight
.artifacts/stratograph-stability-resume-20260922/resume.sh analyze
```

Current status is
`.artifacts/stratograph-stability-resume-20260922/study/status.json`.
Launcher output is `.artifacts/stratograph-stability-resume-20260922/launch.log`;
per-cell output is under `study/dispatch/`. The background process prevents idle
sleep and writes the amended analysis after all declared runs finish.
