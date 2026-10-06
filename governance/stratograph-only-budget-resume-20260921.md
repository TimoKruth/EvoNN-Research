# Stratograph budget-based continuation — 2026-09-21

The user explicitly requested “Fix and resume” after the first continuation
stopped at 18:28 CEST. The authorized scope remains all eleven Stratograph presets
and within-Stratograph conclusions only.

The original 1,500-second study completed 35 runs and retained a failed
`dilated_only` language-breadth run with 127 charged attempts. The 1,800-second
continuation advanced to 39 verified runs before `hybrid`, language breadth,
seed 1701 exhausted its total time at attempt 107 (106 successful, one failed).
Both historical studies remain incomplete, immutable evidence.

## Fix and evidence reuse

A separate clean producer descends from the original producer. Its entire source
difference is recorded in `producer.patch`: Stratograph's run configuration and
run entry point accept a finite total allowance up to 21,600 seconds. Defaults,
per-fit limits, cumulative resume accounting, worker deadlines, search, training,
model code and dataset code are unchanged. No monkeypatch or mutation of a frozen
producer is used. Preparation verifies the exact Git diff and runtime identity.

All 39 completed runs are inherited only after validating full allocated epochs,
complete fit coverage, frozen dataset provenance, original producer identity and
winner replay receipts. Their original source identity is retained. New runs use
the new producer identity. The interrupted hybrid cell restarts from scratch in
a new directory with the same seed. The previous 234 charged attempts are kept in
the cost record, separate from the planned 45,408 study fits (45,642 combined if
no further attempts fail). No failed fit is erased or retried inside its old run.

Every unfinished run has allowance
`budget * (fit_timeout + 30 seconds) + 600 seconds`: for 128 fits with a 120-second
fit cap this is 19,800 seconds (5 hours 30 minutes). This covers the full declared
fit budget at each fit's maximum, worker grace and orchestration overhead. It is
a safety ceiling, not an expected duration or extra fit budget. Engine dispatch
has another 60 seconds of process grace; winner replay remains capped at 180
seconds. Every remaining slot uses the same rule regardless of observed score.

The 11 arms, qualification completion, 16 main paired seeds, execution order,
128-fit budgets, 12 allocated epochs, dataset splits, 30 reference contrasts,
pointwise 95% intervals and Holm correction are unchanged. This is an explicit
amendment across two run-limit validator versions and mixed safety caps, not an
equal-wall-time comparison. Scores or significance did not motivate the change.
The final report retains the entire declared comparison and both failure costs.
Incomplete fits, truncated epochs, replay failure, source/data drift or further
runtime failure stop execution and block complete-study claims.

## Operation

The external controller and amendment manifest are content-bound. Exclusive
leases cover all three study directories; child processes retain those leases.
A `PAUSE` file in any study directory stops new dispatches after the current run.
A recorded failure disables automatic retry. The background process inhibits idle
sleep and automatically writes analysis after all declared cells complete.

```sh
.artifacts/stratograph-only-budget-resume-20260921/resume.sh preflight
.artifacts/stratograph-only-budget-resume-20260921/resume.sh analyze
```

Current status:
`.artifacts/stratograph-only-budget-resume-20260921/study/status.json`.
Launcher output: `.artifacts/stratograph-only-budget-resume-20260921/launch.log`.
Per-run output: `study/dispatch/<slot>/`. Historical launcher files are retained;
use the budget continuation for current status and future pause/resume operations.
