# JEPA pilot design

This is an additive, fixed-architecture feasibility experiment. Its entry points,
operating limits and current acceptance state are in the root README and
CONSOLIDATED_PLAN. It neither changes canonical benchmark definitions nor replaces
the existing engine campaigns. All receipts are exploratory validation evidence.

## Questions and controls

1. Does complementary-view latent prediction help an engine's downstream quality,
   missing-input robustness or representation diversity relative to ordinary
   supervised training and raw-input reconstruction?
2. Does predicting a frozen Prism teacher from missing inputs help beyond ordinary
   full-input representation distillation?

Every declared benchmark, seed and label fraction executes Prism, Topograph,
Stratograph, Primordia and Contenders in every arm. Candidate slots, initial model
weights, task-head initialization and downstream batch streams are identical
across treatments within an engine. Candidate slots are fixed independently of
scores. There is no evolution or inherited optimizer state in this pilot.

| Arm | Initial phase | Downstream phase |
|---|---|---|
| supervised_short | None | F supervised updates |
| supervised_long | None | P + F supervised updates |
| reconstruction | P masked raw-input reconstruction updates | F supervised updates |
| jepa | P complementary-view latent prediction updates | F supervised updates |
| distillation, optional | P full-input frozen representation distillation updates | F supervised updates |
| jepa_transfer, optional | P masked-input frozen representation prediction updates | F supervised updates |

P/F are explicit config values. Supervised-long matches the number of optimizer
updates, not total compute. JEPA has two differentiable encoder passes plus one
teacher pass during pretraining; reconstruction and transfer use one. Receipts
record encoder forward examples, phase updates, timings, allocated parameter
storage and deployed parameter counts. Diagnostics, compilation, process startup
and teacher export also incur cost; worker elapsed time includes the whole worker.
The parameter-storage estimate is not measured peak process/device memory.

Contenders independently reruns a two-estimator raw-feature reference pool in
every arm: logistic regression / ridge and histogram gradient boosting. This pool
is not the canonical contender floor or a compute-matched neural control. Its
fixed estimator caps, actual fits and time are disclosed. A failed estimator
fails the worker; it is not dropped from the reference pool.

## Numerical formulation

Inputs are standardized using all admitted training inputs, including unlabeled
ones. The encoder receives `[x * keep, keep]`, making missingness distinguishable
from an observed standardized zero. Digits use rectangular masks on the original
8x8 layout; tables use feature subsets. A mask is shared across a pretraining
batch and resampled each update, so mask identity alone cannot supply variance
across samples. The pilot's candidate networks process the flattened input and
mask: it is not a patch-tokenized ViT reproduction.

The existing compiled network, including its original output projection, becomes
an encoder into a fixed D-dimensional representation. An additional task head
produces class logits or regression predictions. All encoder parameters train;
Stratograph explicitly uses its trainable v2 hierarchy and RMS normalization.
Prism slots alternate dense/sparse MLPs, Topograph dense/residual DAGs, Primordia
dense/gated circuits, and Stratograph hierarchy depths. Width varies with slot.
These are small fixed architecture controls, not the engines' complete search
spaces or their promoted winners.

The JEPA predictor maps a masked context representation to the EMA encoder's
representation of the complementary view, conditioned on the target mask. The
teacher is initialized from the student's encoder and updated after every SSL
step. Stop-gradient excludes teacher parameters from gradient optimization.
Variance (standard-deviation floor) and off-diagonal covariance penalties apply
to the two online views. The predictor is linear and unbounded; it cannot read
hidden values. Constant representations incur a variance penalty. This does not
prove useful representation learning, so effective rank, feature standard
deviation and downstream metrics are reported before/after adaptation.

Reconstruction uses the same encoder with a linear decoder, scoring only hidden
raw features. Full-input fine-tuning uses cross-entropy or standardized-target
MSE, fresh Adam state at the phase boundary, fixed step counts and gradient
clipping. Regression target statistics use only the admitted labeled subset.
There is no validation-based early stopping or affine calibration in this pilot.

The custom objective combines ideas from
[I-JEPA](https://arxiv.org/abs/2301.08243),
[T-JEPA](https://arxiv.org/abs/2410.05016), and
[VICReg](https://arxiv.org/abs/2105.04906).
It is not an exact reproduction of those papers or
[LeJEPA/SIGReg](https://arxiv.org/abs/2511.08544).

## Frozen teacher experiment

For each task/seed/label fraction, Prism candidate 0 from supervised-long exports
representations of exactly the training rows. Every engine consumes that same
immutable NPZ through a file boundary; no sibling engine imports or weight
translation are involved. The source data split, actual label subset, artifact
hash and source case are checked. No validation embeddings are exported.

Distillation uses full inputs, while jepa_transfer uses masked inputs. Both use
the same predictor, variance/covariance penalty, source and step allocation. The
teacher's output coordinates are fixed throughout each recipient fit. Each
recipient is freshly initialized and adapts end to end afterward. Matching a
frozen teacher's full representation is an ordinary distillation control; masking
is the separately measured predictive component.

Source training is reported as prior cost. It is executed once and reused in the
observed campaign, not counted as many actual source fits. Each recipient receipt
retains the source updates/time; teacher export cost is in the source receipt.
There is no charged-prior gain claim or native motif ingestion/Phase 5 proof.

## Data, evidence and limitations

Datasets are bundled sklearn digits, breast cancer and diabetes with distinct
`jepa_pilot_*_v1` identities. Each uses a deterministic 80/20 train/validation
split; classification is stratified. Label fractions are applied only within
training, retaining at least one example per class. Actual counts/fractions and
raw/split/label-subset hashes are saved. Withheld training labels are not returned
to training. All validation labels remain available for descriptive assessment;
these are not total annotation-budget comparisons. No test results or existing
protected benchmark splits are accessed.

The same fixed 25% corruption probe is used across arms and candidates. Digits
rectangles approximate requested area because coordinates are discrete. Missing
inputs are replaced by training means after standardization. Tabular
predictability need not imply target relevance, and the current datasets and
small networks may be too easy or too small to reveal useful SSL effects.

Each fit saves weights and replays them both in its existing model and in a
freshly compiled model. Results and teacher artifacts are hash-bound to a frozen
manifest; producer source and dependency drift reject resumed execution. All
candidate rows are reported with matched-architecture contrasts. Positive deltas
mean improved accuracy or reduced MSE; no heterogeneous metric aggregation,
p-values, best-of-seed selection, L3/L4 admission or superiority claim is made.

Execution is serial, process-isolated and bounded. Resume occurs between fits,
not during an optimizer update. A failed, interrupted or invalid receipt stops
execution and leaves the matrix incomplete. Failed work is retained as charged
with unknown actual work if interrupted. Start a new explicitly identified pilot
workspace after a repair; never overwrite the failed evidence. Partial successful
runs can resume unchanged with the same command. Sessions cap at 30 minutes.

The four `jepa_training.py` modules intentionally contain identical source, guarded
by an integration test. Engine-owned compilation/training and Compare's file-only
boundary are preserved; Shared contains only data and experiment contracts.

Adaptive search, evolved mask curricula, multi-level JEPA, learned archive
coordinates and mutation-transition world models remain follow-on hypotheses.
The current experiment must first show that its latent objective or transfer has
value beyond the controls, under adequate training and measured cost.
