# 06 — Training, Evaluation, Budgets, Statistics, and Reproducibility

## 1. Evaluation identity

The base accounting unit is one attempted `(candidate, data-role/fold, fidelity-stage, seed)` slot. Fresh training, cache reuse, inherited initialization, invalid-before-training, failure-after-spend, retry, and final refit MUST be separate counters.

## 2. Training contract

A training policy MUST declare:

- optimizer and exact versioned semantics;
- loss and task binding;
- batch construction and shuffle RNG;
- maximum epochs/steps/tokens/examples;
- early-stopping rule and monitored data;
- checkpoint and best-state restoration;
- gradient clipping;
- learning-rate schedule;
- precision and quantization behavior;
- augmentation policy;
- resource/time limits;
- divergence/nonfinite behavior.

TRAIN-001: Best validation state MUST be restored when early stopping is used unless the policy explicitly selects final state.  
TRAIN-002: Validation and test data MUST not influence optimizer updates.  
TRAIN-003: Training order MUST be deterministically seeded when decision-grade.  
TRAIN-004: Timeout with a valid partial result MUST be represented as `budget_exhausted_valid`, not generic failure.  
TRAIN-005: Every actual step/token/example and wall-time spend MUST be recorded.

## 3. Multi-fidelity and promotion

Fidelity is a first-class identity. It may include data fraction, epochs/steps, resolution, sequence length, model width, precision, benchmark subset, or proxy evaluator.

EVAL-001: Cache keys MUST include fidelity and complete training/evaluation policy identity.  
EVAL-002: A lower-fidelity result MUST NOT satisfy a higher-fidelity evaluation.  
EVAL-003: Promotion rules MUST be declared before observing promoted outcomes.  
EVAL-004: Screening omissions MUST be distinct from unsupported or failed outcomes.  
EVAL-005: Promotion MUST consume budget and preserve lineage to earlier stages.

## 4. Metric semantics

The system stores separately:

- raw loss;
- native metric value;
- metric direction;
- canonical normalized utility, when defined;
- engine-local search objective;
- constraint measurements;
- recommendation score and policy.

Raw accuracy, MSE, perplexity, latency, and other heterogeneous values MUST NOT be averaged directly across tasks.

Normalization MUST use a declared benchmark-specific reference such as fixed bounds, strong baseline, empirical reference distribution, rank, regret, or standardized effect. Missing-task penalties and task weights MUST be explicit.

## 5. Budget envelope

A versioned budget contains declared caps and observed values for:

- candidate/evaluation slots;
- optimizer steps;
- examples/tokens processed;
- accelerator/CPU active time;
- job wall clock and queue time;
- per-candidate wall time;
- memory and disk;
- parameter/model-size ceiling;
- latency target;
- worker concurrency;
- network/download bytes;
- prior/reuse policy.

BUD-001: At least one finite hard stopping budget is required.  
BUD-002: Reaching any hard cap MUST stop new scheduling.  
BUD-003: Graceful checkpoint overrun MUST be reported separately.  
BUD-004: Failures and retries consume budget according to actual spend.  
BUD-005: Export-time work MUST not be hidden from accounting; export itself MUST not train.  
BUD-006: Budget amendments MUST be append-only and auditable. Each amendment references the immutable base-envelope digest and previous effective-budget digest; the effective budget is derived by deterministic ordered folding and has its own digest. Resume verifies the complete chain.

## 6. Fairness of comparisons

A comparison eligibility assessment MUST evaluate:

- exact dataset, split, preprocessing, and metric versions;
- task coverage;
- search and data seeds;
- declared and observed compute;
- fidelity;
- cache/inheritance/prior policy;
- runtime/backend/platform class;
- model/resource caps;
- failure/missingness policy;
- contender inclusion;
- test-access status.

Fairness is multi-dimensional:

- data parity
- metric parity
- seed parity
- budget parity
- runtime parity
- capability asymmetry
- accounting completeness
- comparison eligibility

These MUST NOT be compressed into one ambiguous status.

## 7. Statistical selection

- Primary metric and tie-breakers MUST be fixed before test access.
- Repeated evaluations SHOULD pair seeds and splits.
- The inference unit MUST match the true independent unit; correlated rows/tokens/frames MUST not be treated as independent.
- Confidence intervals, effect sizes, practical-significance thresholds, and multiple-comparison policy MUST be declared.
- Missing and failed runs MUST not be silently dropped.
- Product recommendation MUST consider uncertainty and constraint feasibility, not only point estimates.
- Test evaluation is single-shot by default.

## 8. Seed and RNG model

Every job has a root seed. Named derived streams MUST include at least:

- search
- data generation
- split
- model initialization
- data order
- augmentation
- mutation/crossover
- benchmark sampling
- worker/process
- stochastic inference
- bootstrap/statistics

Derivation MUST be deterministic and independent of process scheduling. Checkpoints MUST preserve required Python, NumPy, MLX, PyTorch, engine, scheduler, and worker RNG states.

## 9. Resume equivalence

A checkpoint MUST identify the exact next operation and represent one atomic lifecycle boundary.

REPRO-001: Under deterministic settings, resumed and uninterrupted execution MUST produce equivalent event and candidate sequences within declared backend tolerances.  
REPRO-002: If exact continuation is unavailable, the resumed job/attempt MUST carry `resume_equivalence: nondeterministic` and be excluded from strict repeatability claims; this annotation does not replace its lifecycle state.  
REPRO-003: Resume MUST restore scheduler state, archives, caches that alter semantics, counters, and benchmark rotation state.  
REPRO-004: Configuration drift MUST be rejected except for a documented safe allowlist.

## 10. Finalization and test evaluation

Model selection uses validation evidence only. Optional refit on train+validation MAY occur if structure, stopping derivation, preprocessing refit behavior, threshold/calibration policy, and seed schedule were frozen before test access.

Any post-test change to structure, preprocessing, thresholds, calibration, seed count, metric, or selection policy creates a new exploratory candidate and invalidates confirmatory status.
