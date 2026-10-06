# Topograph total-time continuation — September 27

The user requested resumption. The September 23 confirmation restart completed
two cells (`next` and repaired `legacy`, language breadth, seed 32801), then its
`open` cell exhausted the cumulative 1,500-second cap at attempt 180. The last
worker received only 17.396 seconds rather than the 120-second per-fit allowance.
It failed, leaving 179 successful fits, one charged failure and no complete export.
The historical attempt remains intact and cannot simply resume past that failure.

This explicit amendment retains both verified complete cells under their original
producer identities. Each unfinished cell gets a total cap of
`256 * (120 + 30) + 600 = 39,000 seconds` (10 hours 50 minutes). This is a safety
ceiling, not an ETA. The per-fit cap remains 120 seconds. All 126 remaining cells
retain their seeds, models, optimizer settings, epoch and fit budgets, benchmark
data and ordering. The exhausted cell restarts in a fresh directory with its same
seed; its 180 charged attempts remain recorded separately as historical cost.

The new producer changes only accepted run-time bounds and the explicit
Topograph-only campaign bound, plus tests. Training arithmetic and the earlier
legacy resource-admission repair are unchanged. Original producers, manifests,
checkpoints and results remain untouched. The new manifest binds the previous
continuation, historical receipts, failed work, exact source patch and controller.
Inherited cells receive full export validation in their original producer.

The controller checkpoints every 32 fits using the engine's existing resume
contract. Pause takes effect between segments, without killing a fit. Every cell
must still finish all 256 charged fits, pass strict export admission and replay
its winner before it is complete. No failed fit is silently retried or discarded.
All exports are validated again before final inference.

The nominee remains `mixer`; the 128-cell confirmation matrix, aggregate endpoint,
16 paired seeds, three contrasts, confidence intervals and corrections are fixed.
The final report identifies mixed total safety caps and source identities and
retains all historical failed work. No equal-wall-time or cross-engine claim is
allowed. A complete comparison may remain statistically inconclusive.

Verification: 111 Topograph tests in the frozen producer; seven controller
regressions; a native eight-fit, two-segment run with checkpoint resumption,
complete export admission and passed winner replay; all-data preflight.

Current workspace: `.artifacts/topograph-budget-resume-20260927/study`.
Current status: `study/status.json`; log: `run.log`; controls: adjacent `studyctl`.
The old directories' `CURRENT.json` files point here. Original pause markers
remain historical; the user's resumption starts this new continuation.

See the [launch receipt](topograph-budget-resume-20260927.json) for exact identities.
