# Stratograph comparison continuation — 2026-09-21

The user requested: “Why is it not running? can we resume please?” This explicit
amendment continues the previously authorized eleven-preset Stratograph-only
comparison. It supports within-Stratograph conclusions only.

The original study stopped after 35 verified runs (22 qualification, 13 main).
`main-language_breadth_v1-s1701-dilated_only` exhausted its 1,500-second run cap
while fitting attempt 127. Its 126 successful attempts and one charged failure
remain in the original directory; the original study stays incomplete.

The continuation inherits the 35 completed runs only after verifying their
exports, winner replay receipts, dataset provenance and full allocated epochs.
It restarts the interrupted cell from scratch in a separate directory. Every
unfinished cell receives the engine's existing maximum run cap of 1,800 seconds.
The 120-second per-fit cap, 12 allocated epochs, fit counts, 11 arms, seed order,
datasets, frozen engine producer and 30-contrast statistical plan are unchanged.
No score or significance result motivated this change.

This is an amended fixed-fit comparison with mixed safety caps. It cannot support
an equal-wall-time claim. All prior 127 charged attempts are disclosed separately
from the 45,408 planned study fits (45,535 total if the continuation succeeds
without another failed attempt). Historical evidence is not overwritten. Another
failure stops the continuation and blocks complete-study conclusions; it is not
automatically retried. Incomplete epochs also block completion.

The controller is copied outside the immutable original producer and its exact
bytes are bound in `continuation.json`. Each engine dispatch has a 1,820-second
process deadline, followed by at most 180 seconds for replay. The continuation
controller loops across these bounded operations; this explicitly replaces the
original controller's 1,800-second session limit. Exclusive leases on both study
directories prevent concurrent launchers. A `PAUSE` file in either study directory
stops new dispatches after the current run finishes.

Operations from the project root:

```sh
.artifacts/stratograph-only-continuation-20260921/resume.sh preflight
.artifacts/stratograph-only-continuation-20260921/resume.sh analyze
```

Live status: `.artifacts/stratograph-only-continuation-20260921/study/status.json`.
Live launcher output: `.artifacts/stratograph-only-continuation-20260921/launch.log`.
Per-run fit output lives below `study/dispatch/`. The controller runs in the
background with idle-sleep inhibition and exits on failure. It automatically
writes the amended analysis after all runs finish; incomplete analyses retain
all 30 contrasts and cannot label a material gain.
