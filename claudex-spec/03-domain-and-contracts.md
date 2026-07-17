# 03 — Domain Model and Contracts

## 1. Identity rules

All durable identities MUST be immutable ULIDs or UUIDv7 values with a human-readable short form. User labels are mutable metadata and MUST NOT serve as identity.

Required identities include:

- project ID
- dataset ID and dataset-version ID
- split ID
- plan ID
- job ID and attempt ID
- candidate ID and candidate-spec digest
- evaluation ID
- artifact digest
- model-version ID
- export ID
- plugin and capability IDs

DOM-001: The same run/model identity MUST be used in metadata, events, files, reports, bundles, and analytical rows.  
DOM-002: Content-derived identities MUST specify canonical serialization and digest algorithm. Any field that stores the resulting digest is omitted from the hashed serialization; the digest is computed over the remaining canonical document and then attached externally or populated afterward.  
DOM-003: Tags and labels MAY change; digests and version IDs MUST NOT.

## 2. Version domains

The following versions are independent and MUST be recorded exactly:

- product/package version;
- specification version;
- config schema version;
- database schema version;
- dataset descriptor version;
- task registry version;
- metric registry version;
- engine protocol version;
- backend capability version;
- artifact/bundle version;
- plugin version.

Compatible version ranges MAY be used during authoring, but execution MUST resolve and freeze exact versions.

## 3. Shared run envelope

Every job MUST have a strict, versioned `RunEnvelope` containing:

- identity and lineage;
- project and objective;
- dataset/split references;
- task and metric references;
- root seed and derived RNG map;
- budget/resource envelope;
- runtime/platform requirements;
- network policy;
- artifact/retention policy;
- portfolio configuration;
- engine-specific namespaced settings;
- constraints and preferences;
- software/environment lock digest;
- creation actor and timestamps.

Unknown top-level fields MUST be rejected. Versioned extension namespaces MAY preserve engine-specific configuration.

## 4. Candidate identity

Architecture, training policy, and runtime state MUST be separate.

A candidate consists of:

1. immutable model/candidate specification;
2. optional evolvable training-policy specification;
3. external-asset references;
4. lineage and proposal metadata;
5. evaluation policy.

Fitness, measured parameters, checkpoints, and runtime counters MUST NOT be part of the candidate-spec digest unless explicitly declared as evolvable genes.

## 5. Evaluation artifact

One `EvaluationArtifact` family MUST own the complete truth for a single attempted candidate × data role/fold × fidelity × seed slot. `record_kind: preflight` represents invalid/ineligible/unsupported/skipped slots before model execution and MUST NOT fabricate compiled models, fitted state, resources, metrics, or artifacts. `record_kind: execution` represents work that entered the execution pipeline and records observed spend even if compilation/training failed:

- candidate and compiled-model identity;
- backend and capability identity;
- dataset, split, preprocessing, and fitted-state identity;
- initial checkpoint or inherited state;
- all RNG stream identities and states required for resume;
- declared and observed budget;
- weights/checkpoint digest;
- native metric values;
- normalized utility values;
- resource measurements;
- warnings and diagnostics;
- terminal outcome;
- timestamps and worker identity.

Fitness, persistence, archives, reporting, selection, and export MUST consume this same artifact for training/validation/fold work. Re-training merely to create a report is forbidden. Confirmatory test scoring uses the restricted `ConfirmatoryEvidence` specialization, which contains aggregate authorized results and audit identity only—no test predictions, labels, checkpoints, fitted state, or reusable per-example feedback.

## 6. Outcome taxonomy

### Job outcomes

`completed | failed | cancelled | invalidated | abandoned`

A job may temporarily enter the non-terminal `interrupted` reconciliation state. Resume determinism is recorded separately as `exact`, `tolerance_equivalent`, or `nondeterministic`.

### Attempt outcomes

`ok | budget_exhausted_valid | pruned | ineligible | unsupported | skipped | failed | interrupted | cancelled | invalid`

### Failure reason classes

- configuration
- policy
- dataset
- integrity
- privacy/license
- genotype/model specification
- compilation
- training divergence
- numerical invalidity
- out of memory
- timeout/budget
- backend/runtime
- persistence
- worker/process
- export/conversion
- internal product defect

Every failure MUST include a stable machine reason code and sanitized diagnostic reference.

## 7. Protocols

### Engine adapter

An engine adapter MUST implement:

- `describe_capabilities`
- `validate_config`
- `initialize_state`
- `propose_candidates`
- `observe_results`
- `checkpoint_state`
- `restore_state`
- `summarize_state`
- `finalize`

It MUST NOT train candidates directly unless it also implements the evaluator protocol inside an isolated engine runtime.

### Training evaluator

A training evaluator MUST implement capability validation, training-authorized input materialization, compile/build, train/adapt, validation-prediction publication, resource measurement, checkpoint publication, evaluation artifact publication, cancellation, and cleanup. It MUST NOT receive test labels.

### Validation evaluator

A validation evaluator MUST score frozen validation predictions or frozen candidate checkpoints under the predeclared selection/calibration policy. If it initiates additional parameter fitting, that fitting is a new training attempt and remains test-blind.

### Final-refit evaluator

A final-refit evaluator MAY access train+validation data only after candidate structure, preprocessing-refit rules, hyperparameters, epoch/step derivation, calibration policy, and seed schedule are frozen. It may fit parameters under that exact policy, but cannot compare alternatives, alter selection decisions, or access test inputs/labels. Its output is a new finalized model artifact.

### Confirmatory test evaluator

A confirmatory test evaluator MUST accept only a frozen model version, frozen preprocessing/decoding state, protected test inputs/labels, and predeclared metrics. It MUST NOT train, adapt, calibrate, select, mutate, expose labels, or return per-example/partial/subgroup feedback to the search product before the confirmatory result is irrevocably committed. It returns only the authorized aggregate evidence and audit record.

### Runtime backend

A backend MUST declare:

- supported operators, tasks, dtypes, devices, shapes, dynamic behavior;
- determinism class;
- serialization formats;
- export paths;
- known numerical differences;
- measurement capabilities.

Unsupported capabilities MUST fail during planning or preflight.

## 8. Configuration policy

CFG-001: Pydantic models MUST use deliberate strictness at external and persisted boundaries.  
CFG-002: Silent coercion that changes scientific meaning is forbidden.  
CFG-003: Cross-field constraints MUST be validated before execution.  
CFG-004: Resolved configuration MUST be canonicalized and hashed.  
CFG-005: Resume MUST verify the immutable base-envelope digest and the ordered budget-amendment chain. Logging verbosity MAY differ outside the scientific envelope; budget changes are represented only by valid amendment objects, not config drift.  
CFG-006: Config migrations MUST be explicit, version-directed, and separately tested.  
CFG-007: Example defaults MUST NOT become hidden runtime defaults.

## 9. Events

Events are append-only and MUST include:

- event ID and schema version;
- UTC timestamp;
- aggregate IDs;
- monotonic per-aggregate sequence;
- event type;
- actor/worker;
- correlation and causation IDs;
- payload digest or inline payload;
- redaction classification.

Duplicate delivery MUST be harmless through idempotent event handling.
