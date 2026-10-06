# Prism fixed-fit continuation — September 21, 2026

The user requested “fix and resume” after the replacement study stopped with
22 qualification and 30 main runs completed and replayed. The next scheduled
cell, `frontier_v2`, language breadth at 128 fits, seed 21601, exhausted the
1,500-second total allowance after 98 successful attempts. Its checkpoint elapsed
time was 1499.714 seconds, but its durable invocation clock closed at 1502.682
seconds. Ordinary resume therefore has no remaining time. No fit failed.

This explicit amendment retains all 52 verified completed runs with their
original producer identities. It restarts only the exhausted cell from scratch
in a separate directory, retaining its 98 charged attempts and measured training
time as additional cost. Original producers, manifests, results and failure logs
remain unchanged and incomplete; no checkpoint clock or configuration is edited.

Every unfinished cell receives `budget * (fit_timeout + 30) + 600` seconds:
19,800 seconds for 128 fits, 39,000 for 256 fits. This covers the declared fit
count at the unchanged 120-second per-fit cap, worker grace and orchestration
overhead. It is a safety ceiling, not an expected duration or extra fit budget.
The engine process gets another 20 seconds to exit; replay remains capped at
300 seconds. A new failure stops the controller and blocks automatic retry.

The isolated producer descends from `f5915a2` with exactly three changed files:
Prism configuration and run admission allow finite cumulative caps up to 43,200
seconds, and campaign admission allows this only for the explicit Prism study
scope. Search, architecture, training, optimizer, cumulative clocks, datasets,
defaults and per-fit caps remain unchanged. `producer.patch` binds that exact
diff. The external controller's bytes are bound in `continuation.json`.

All eleven variants, 30 paired seeds, ordering, fit counts, epoch allowances,
dataset splits, 110-contrast Holm family and bootstrap/decision rules are
unchanged. This is an amended fixed-fit comparison using mixed safety caps and
producer revisions; it cannot establish equal-wall-time superiority. Scores
were not used to choose the amendment. Inference remains blocked until every
declared cell has complete successful fit coverage and verified winner replay.
The final report retains historical origins and the extra 98 attempts. Earlier
validator-repair costs and evidence remain in the preceding recovery records.

Validation before execution: 23 targeted tests cover scoped timeout admission,
exact scheduled-slot dispatch, refusal to retry an interrupted amended run,
and blocking inference on incomplete coverage. A native 16-fit smoke run with a
19,800-second total allowance paused and resumed with cumulative accounting
intact, validated its export and passed winner replay. Lint passed.

Current execution directory:
`.artifacts/prism-confidence-budget-resume-20260921/`.

```sh
# Current status and launcher output
cat .artifacts/prism-confidence-budget-resume-20260921/study/status.json
tail -n 20 .artifacts/prism-confidence-budget-resume-20260921/run.log

# Validate or analyze without training
.artifacts/prism-confidence-budget-resume-20260921/resume.sh preflight
.artifacts/prism-confidence-budget-resume-20260921/resume.sh analyze

# Request pause after the active run and replay
touch .artifacts/prism-confidence-budget-resume-20260921/study/PAUSE
```

The controller holds exclusive leases on both study controllers and the active
campaign. Training subprocesses inherit these leases. A `PAUSE` file in either
study blocks new dispatches. Background execution uses Standard launchd priority,
sleep prevention and no automatic restart after failure. New progress lives in
the continuation status file; older launcher logs are historical evidence.

The [launch receipt](../../governance/prism-confidence-budget-resume-20260921.json)
records the background start at 22:42 CEST, frozen producer `3991748`, all 52
historical validations and all 33 amended campaign preflights. Read-only
preparation attempts and their logs are retained alongside the final study;
they dispatched no model fits. The final amendment is bound by checksum
`7aa4537b8490b6f8a0f8370861681cdfc941c92bf3b3931934d000aef33e1bd0`.

Startup verification confirmed the continuation actively training the restarted
`frontier_v2` breadth cell with a 19,800-second total cap and 120-second fit cap.
The live status reports 22 qualification and 30 main completions inherited; this
verification does not claim the restarted cell or full study is complete.
