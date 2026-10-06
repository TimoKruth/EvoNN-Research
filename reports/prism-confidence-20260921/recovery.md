# Prism confidence study recovery — September 21, 2026

Operational follow-up: the [budget continuation](budget-continuation.md) records
the later total-time exhaustion, retained completed results and current execution
paths. The producer and study described below remain preserved historical evidence.

The original study stopped after five successful core qualification runs. The
sixth (`search_v2`, seed 21600, 32 fits) completed training but failed export
admission: “inheritance ratio differs from declared training policy”. No main
run was dispatched. The user explicitly requested a fix and restart/resume.

The engine already applies the full-training and fresh-exploration policies to
all six `_v2` variants. Shared evidence validation recognized those policies only
for the older variants, so it incorrectly expected legacy epoch discounts on
protected inherited candidates. The correction extends the existing validation
rules to the six declared variants; it also enforces their fresh-initialization
restriction. It changes no search, optimizer, model, data or training behavior.
The previously rejected export passes the corrected validator with all 32 fits
successful, including four protected inherited attempts.

The frozen protocol requires a separate replacement study for source changes.
The replacement producer is commit `f5915a224b886cccfa4a0c767d4f5fc09a2b97d7`,
derived from the original `8b8c3db` with only the validator correction and its
regression test. Its environment has the same package versions. The original
producer, artifacts, manifests and failure log remain unchanged and incomplete.
An unlaunched preparation draft is retained under `prelaunch-1-*` beside the
replacement; it contains no study runs.

The replacement retains all eleven variants, the same schedule, original seeds,
datasets, budgets, epoch limits, timeouts, qualification gate and statistical
decision rules. All qualification runs are repeated; no old result is adopted.
The original 30 main seeds remain unexecuted. Repeated qualification is debugging
evidence, not fresh confirmation. The original seed audit is retained with an
explicit replacement declaration rather than falsely claiming a new audit of
unused qualification seeds. No scores were used to select variants or seeds.

Current workspace: `.artifacts/prism-confidence-repair-20260921/study`.
Preparation script, replacement receipt, preflight, test output and launch
configuration are stored alongside it, outside the frozen producer.

```sh
# Full sequence / resume; qualification gates main execution.
.artifacts/prism-confidence-repair-20260921/run.sh

# Ask the controller to pause after its active run and replay.
touch .artifacts/prism-confidence-repair-20260921/study/PAUSE

# Remove the pause request before an explicitly requested resume.
rm .artifacts/prism-confidence-repair-20260921/study/PAUSE

# Read current progress and failure output.
tail -n 20 .artifacts/prism-confidence-repair-20260921/run.log
```

The launchd job is `gui/501/com.evonn.prism-confidence-repair-20260921` with
Standard process type, sleep prevention, an explicit Homebrew PATH and no
automatic restart on failure. It runs qualification followed by main execution
only if every qualification slot and winner replay succeeds. Its launch receipt
and live log establish execution status; this recovery note makes no claim that
qualification or statistical analysis has completed.

All 54 targeted tests passed on the frozen producer using the native backend,
including valid evidence and both negative cases for every v2 policy. All 55
campaign preflights and lint passed. The
[replacement launch receipt](../../governance/prism-confidence-repair-launch-20260921.json)
records the authorized full restart at 16:16 CEST on September 21.

[Launch verification](../../governance/prism-confidence-repair-verification-20260921.json)
confirmed seven qualification completions and winner replays, including the
previously failing `search_v2` core slot and the following `representation_v2` slot.
The controller remains active; main execution is still gated on all 22 slots.
