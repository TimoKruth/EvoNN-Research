# Stratograph per-fit allowance continuation — 2026-09-22

The user explicitly requested “fix and resume” after the numerical continuation
stopped with 105 completed runs. The failed cell was `evolving`, language breadth,
seed 1704. All 128 attempts were charged: 127 succeeded, while attempt 121 on Aesop
context-64 reached its 120-second training deadline. The failed run and all
previous studies remain immutable evidence.

## Amendment

Every unfinished run now receives a 600-second (10-minute) per-fit allowance.
Its total allowance remains budget-derived:
`budget * (fit_timeout + 30 seconds) + 600 seconds`. For 128 fits this is 81,240
seconds (22 hours 34 minutes), a safety ceiling rather than an expected duration.
The CLI process has another 60 seconds of finalization grace and replay remains
bounded at 180 seconds. Runs finish as soon as their existing fit budgets finish.

A separate clean producer descends from the numerical-recovery producer. The
complete source diff changes only the total-time validators in `config.py` and
`run.py`, raising their maximum from 21,600 to 86,400 seconds. The existing engine
per-fit maximum of 1,800 seconds already permits the new 600-second setting.
Default durations are unchanged. No training arithmetic, gradient recovery,
architecture, search policy, learning rate, epoch count, seed, dataset or fit
budget changes are introduced.

The 105 full-epoch completions are inherited with their actual producer identities,
verified exports and replay receipts. The interrupted cell restarts from scratch
in a new directory with the same seed. Earlier failures charged 127, 107 and 128
attempts; this failure adds 128, totaling 490 retained attempts. The original study
still plans 45,408 fits across 374 runs; eventual success without another failed
run would therefore account for 45,898 study and retained failed-run attempts.
Diagnostic and regression work is separate and retained alongside launch evidence.

## Interpretation and controls

This remains the explicitly requested eleven-preset Stratograph-only comparison.
All 16 main paired seeds, 12 epochs, 128-fit main budgets, benchmark packs,
execution order, 30 reference contrasts, pointwise 95% confidence intervals and
Holm correction are unchanged. Because completed runs have shorter safety caps,
this is a mixed-cap fixed-fit comparison; it cannot support equal-wall-time claims.
The final report must disclose the amendments, numerical recovery, producer
identities and every retained failure. Incomplete epochs or coverage still block
complete-study conclusions. An unavailable statistical test remains in the full
multiplicity family.

The controller, producer diff, original manifests and status records are bound by
hashes. Exclusive leases cover all five study directories and are inherited by
workers. `PAUSE` in any of those directories stops new dispatch after the current
run. Further failures stop the launcher and are never automatically retried.
Historical artifacts and launchers are not edited.

```sh
.artifacts/stratograph-fit-resume-20260922/resume.sh preflight
.artifacts/stratograph-fit-resume-20260922/resume.sh analyze
```

Current status: `.artifacts/stratograph-fit-resume-20260922/study/status.json`.
Launcher output: `.artifacts/stratograph-fit-resume-20260922/launch.log`.
Per-cell fit output: `study/dispatch/<slot>/`. The detached launcher prevents idle
sleep and automatically analyzes the complete study after all cells and winner
replays pass.
