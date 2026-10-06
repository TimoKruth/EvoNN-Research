# Prism frontier implementation — 2026-09-21

Prism now offers five opt-in mechanism variants and a combined `frontier_v2`.
`open` remains the default/control. This is implementation validation, with no
new scientific comparison, quality/speedup claim or protected-test evaluation.

## Evidence driving the changes

The [September 16 Q findings](../qualification-20260916/findings.md) report that
Prism's regression winners do not improve when the core fit budget doubles,
digits improves by 0.694 percentage points but remains below the contender pool,
and language quality leads the observed engine means. Only two seeds support
these observations, and Q remains incomplete at 28/30 runs. The
[readiness audit](../readiness-20260916/report.md) also identifies substantial
real-text contender overfitting; engine margins do not establish baseline adequacy.

Code inspection found that CNNs use a global spatial mean, regression selects
uncalibrated checkpoints before final train-fitted calibration, and the search
spends a recurring slot on continuation even when the last selected epoch is
earlier than the fit allowance. These findings motivate the experiments; they do
not establish which change will improve benchmark scores.

## Implemented alternatives

| Variant | Mechanism |
| --- | --- |
| `search_v2` | Diverse independent founders, bounded local mutations with benchmark/family operator feedback, quality-archive parents, plateau refinement and periodic continuation |
| `representation_v2` | Global plus four spatial cells for CNN readout; zero-initialized MLP input-to-output linear path; pre-normalized attention residual blocks |
| `regularized_v2` | Training-only label smoothing and matrix-only AdamW decay |
| `averaged_v2` | Update-wise EMA with raw/averaged checkpoint selection; reset optimizer moments when EMA wins |
| `calibrated_v2` | Regression checkpoint selection uses the same train-calibrated MSE as final scoring |
| `frontier_v2` | All five mechanisms combined |

Every search variant retains protected family rotation, weak-lineage development,
reservoir/descriptor parents and fresh proposals. There is no family blacklist.
Architecture additions are reversible; the architecture-only arm retains original
founder training settings. Neutral new genes preserve historical genome and
executed-architecture identities. Nonneutral genes use `prism.genome/v3`.

Runs disclose selected weight source, selection metric, training policy settings,
epoch allowances, work and proposal origins. Exported winners remain individual
models with ordinary replay. No validation targets enter gradients, smoothing,
preprocessing or regression calibration; they select candidates/checkpoints.
EMA uses current training-only normalization buffers and does not recalibrate them.
Its extra validation candidates increase selection exposure and measured work.
Partial inheritance remains experimental, and EMA begins anew in each fit.

`python -m evonn_compare.prism_frontier --base-spec BASE.json --output NEW_DIR`
produces matched specs, preserving pack/budgets/seeds, all four engines and
Contenders, and all other policy fields. It rejects partial rosters, duplicate
variants, existing output directories, and fixed-genome search/representation
experiments. This command starts no fits or data preparation. Runtime campaign
planning still requires a clean, frozen checkout and standard preflight.

## Verification scope

Verification uses an isolated worktree based on `d4ba3ba4342defe094e0b1e6a241fe59c3355166`
plus the Prism changes and its portable policy/planning surfaces. Concurrent
changes to other engines in the maintained workspace are excluded from this
verification. The compact receipt is [validation.json](validation.json).

- Prism package CI: lock validation, lint, package identity and 104 passing tests.
- Ten additional portable-policy/campaign-spec tests pass.
- Real frontier CLI fits recover after SIGKILL at the transaction boundary;
  resumed and uninterrupted controls match candidate identities, scores, updates
  and selected weight sources. Exports validate and saved winners replay on both
  NumPy and native MLX CPU.
- Existing fixed-finalist warm/cold integration controls also pass on both
  backends, with charged training, source provenance and optimizer continuation.
- New numerical checks cover nonzero/finite-difference gradients, spatial
  location sensitivity, causal attention, optimizer backend agreement, calibrated
  selection/final-score agreement and training-only calibration coefficients.
- Search state roundtrips exactly, including two-member populations; every
  compatible family retains protected opportunities across image, tabular and LM.
- Import-boundary validation and changed-file lint pass.

The [compatibility probe](compatibility.json) compares original source from HEAD
with the modified engine. All sixteen neutral model families have identical
initial/final weights, score, selected epoch, updates and loss on deterministic
small synthetic fixtures. Legacy/open traces match exactly over 128 proposals for
each of three modalities (six traces, 768 proposals). This is bounded regression
evidence, not proof that all possible old runs are unchanged.

No performance promotion follows. Later all-system comparisons must evaluate
failure rates, per-task quality, diversity, optimizer work and measured time.
Both EMA and calibrated selection add validation cost; fresh confirmation must
account for choosing among several variants. The prior incomplete qualification
and historical results remain unchanged.
