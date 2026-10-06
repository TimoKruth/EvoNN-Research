# JEPA training assessment — 2026-09-16

**Decision: retain JEPA as an experimental low-label tabular hypothesis; do not
promote the current objective into engine defaults or invest in masked teacher
transfer on the strength of these results.** The repeated campaign is complete,
with a small positive Prism signal and substantial negative image results.

## Executed experiment

The frozen `transfer.json` superset ran once: two tasks, three seeds (131, 137,
149), 10%/100% training labels, two fixed candidates per neural engine, six arms,
and Prism, Topograph, Stratograph, Primordia plus Contenders in every cell.
There were **648 successful worker cases / 720 fits**, comprising 576 neural
fits and 144 raw-feature contender fits. No failures or excluded engines.
All 576 neural models passed saved-weight and fresh-compilation replay;
all result, weight and teacher artifact hashes verified. Producer identity was
unchanged after execution. Neural training performed 67,584 optimizer updates.

The campaign used MLX CPU, latent width 16, batch size 32, 64 pretraining and
64 fine-tuning updates (short supervised: 64; long supervised: 128). Observed
summed worker time was 912.4 seconds / 15.2 minutes. Execution was serial on AC
power while another workload occupied the GPU; timings are not controlled speed
measurements. The source commit was `69d3670af065bd5894fff91792d5f1d1f5c3902b`.

## What the results say

Mean JEPA accuracy change against 128-update supervised training, in percentage
points. Each seed first averages its two fixed candidates; the three seed
effects are then averaged. These are validation observations, not significance
tests or protected-test results.

| Engine | Digits, 10% labels | Digits, 100% labels | Breast cancer, 10% labels | Breast cancer, 100% labels |
|---|---:|---:|---:|---:|
| Prism | -18.10 | -18.61 | +0.88 | -0.58 |
| Topograph | -16.44 | -19.86 | +0.15 | -0.73 |
| Stratograph | -17.96 | -20.60 | 0.00 | -0.88 |
| Primordia | -20.32 | -19.54 | -0.88 | -2.34 |

**Images:** all eight engine/label settings lose to longer supervised training
in every seed average. Missing-input accuracy also falls by 8.29–18.98 points.
Against short supervised training, clean-accuracy changes are much smaller
(-2.22 to +1.30 points across settings), so the extra pretraining largely fails
to buy downstream quality. JEPA does beat reconstruction in the mean for Prism,
Topograph and Stratograph, but beating this weaker control does not establish
a reason to use it. The raw-feature contender pool achieves 91.48%/97.50%
accuracy with 10%/100% labels, far above the small neural candidates here.

**Low-label tables:** Prism improves from 95.76% to 96.64%, with +0.88 points
in each seed average; both candidate slots have positive mean gains against
long supervised (+0.29 and +1.46 points). Its missing-input gain is +1.61 points
and positive in all three seeds. It also gains +0.88 points over short supervised
and +1.17 over reconstruction, with positive seed averages throughout. However,
the clean gain amounts to only one extra correct validation prediction per
candidate on average (114 validation rows). The reconstruction advantage is
concentrated in candidate 0; candidate 1 is tied in the mean. With all labels,
Prism loses to longer supervised training. This is a narrow follow-up signal,
not broad JEPA success. Other engines do not reproduce a consistent advantage.

**Frozen teacher transfer:** masked prediction loses 0.79–5.23 points to
full-input distillation across the eight digits settings. Tabular mean changes
range from -1.46 to +0.44 points, and no setting improves in all three seeds.
There is no present evidence that masking improves cross-engine transfer.
This experiment transfers representations through files, not native motifs.

**Cost and diagnostics:** JEPA processes twice the encoder forward examples of
long supervised or reconstruction, with median paired training-time ratios of
1.23–1.56 against long supervised across settings. Whole-worker ratios are only
1.01–1.06 because startup and other overhead dominate these tiny fits. Teacher
transfer additionally relies on 12 source fits: 1,536 updates and 16.2 worker
seconds, counted once in campaign totals and reported separately from recipient
ratios. The pretraining JEPA probes have mean feature std 0.35–0.82 and effective
rank 1.39–7.64; after fine-tuning, std is 0.47–1.41 and rank 1.15–6.94. They are
not constant, but low rank can still limit their usefulness. Late training loss
continues falling; these schedules do not demonstrate convergence.

## What merits another experiment

The next useful question is whether low-label tabular pretraining preserves the
Prism signal across more datasets and adequately trained, compute-accounted
controls. A follow-up should keep **all four engines and Contenders**, add unseen
seeds and tabular datasets, compare predeclared longer schedules, and retain
short/long supervised and reconstruction controls. Reserve untouched evaluation
data before tuning masks or regularization. The three current seeds have
overlapping data splits, and seed 131 was also observed in the initial pilot;
they are exploratory replications, not independent held-out confirmation.

Prioritize that bounded check over a larger version of this image experiment or
further masked teacher transfer. A spatial/patch encoder, jointly trained
supervised-plus-JEPA objective, or architecture-mutation predictor would be new
hypotheses requiring their own controls. The current experiment neither tests
nor validates them. It also does not reproduce I-JEPA, T-JEPA or LeJEPA, run
architecture evolution, meet canonical contender floors, or establish general
JEPA potential beyond these small fixed architectures and data.

## Evidence and reproduction

- [Full descriptive tables](repeated-20260916.md): every engine, label setting
  and declared contrast, including negative results and contender references.
- [Machine-readable summary](repeated-20260916.json): per-seed and per-candidate
  effects, timings, diagnostics, predeclared analysis, resource snapshot,
  producer identity and all 648 result receipt hashes.
- [Design and limitations](DESIGN.md) and [frozen preset](transfer.json).
- Local complete artifacts: `.artifacts/jepa-repeated-20260916`, including
  raw reports, requests, receipts, training curves, weights and teacher arrays.
  These large local files are not committed; the compact summary is not a
  substitute for them when independently replaying the models.

Manifest SHA-256:
`3502a4b9b0e30f7bf8c2e6ea396427310b696f18dde28ffc0d4313c4a8bd0841`.

Regenerate the verified summary from retained local artifacts:

```sh
uv run python research/jepa/analyze.py .artifacts/jepa-repeated-20260916 \
  --output research/jepa/repeated-20260916
```

To execute anew, use `evonn-compare jepa plan --spec research/jepa/transfer.json`
with a new workspace and then `evonn-compare jepa run` on that workspace.
Preserve the recorded producer and dependency identities when comparing results.
The summary rejects incomplete matrices, mismatched data/initialization and
nonidentical repeated contender controls. Its three regression tests pass.
