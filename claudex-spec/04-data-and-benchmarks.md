# 04 — Data, Benchmarks, Governance, and Leakage Protection

## 1. Canonical dataset descriptors

DATA-001: Every usable dataset MUST have one immutable canonical descriptor. Loader code alone is not a definition.  
DATA-002: A descriptor MUST include stable logical `dataset_id`, immutable `dataset_version_id`, semantic version, lifecycle state, canonical digest, title, owner/authority, modalities, feature/target schemas, sample identity, sources, provenance, governance, splits, preprocessing, and limitations. Every semantic version receives a distinct `dataset_version_id`; jobs reference that ID, never only the logical dataset ID.  
DATA-003: Any change to bytes, semantics, labels, splits, preprocessing, privacy, license, or schema MUST create a new version.  
DATA-004: Descriptor serialization MUST be deterministic and content-addressed. `canonical_digest` is omitted when computing the descriptor's canonical bytes, then populated with the resulting digest.  
DATA-005: Aliases MUST resolve unambiguously to an exact canonical ID and version.

## 2. Source and governance contract

Each source artifact MUST declare:

- origin URI or authority;
- resolved revision/version;
- publisher and acquisition timestamp;
- media type and packaging;
- expected size and file count where knowable;
- checksum algorithm and value;
- authentication class without secret values;
- license and attribution;
- redistribution and model-training rights;
- privacy classification;
- retention/deletion requirements.

Unknown or conflicting license/privacy status MUST fail closed for decision-grade work.

DATA-010: Mirrors are equivalent only when verified bytes are identical.  
DATA-011: Mutable upstream data MUST be snapshotted or represented by a fully reproducible acquisition recipe.  
DATA-012: Governance changes MUST create append-only events and re-evaluate cached artifact eligibility; historical records MUST NOT be rewritten.  
DATA-013: Credentials MUST NOT appear in descriptors, cache keys, logs, reports, or bundles.

## 3. Controlled acquisition

Downloads MUST be allowlisted, TLS-validated, redirect-constrained, size/MIME checked, timeout-bounded, retry-bounded, credential-safe, lock-safe, atomic, and fully logged.

Archives MUST be treated as hostile. Extraction MUST prevent:

- path traversal;
- absolute paths;
- symlink/hardlink escape;
- device files;
- overwriting unrelated files;
- decompression bombs;
- excessive nesting/file count;
- filename normalization collisions;
- executable dataset hooks.

Partial or quarantined artifacts MUST never be consumed as verified inputs.

## 4. Stable sample identity and lineage

Sample IDs MUST be assigned before randomized processing and MUST NOT derive from row position, split membership, target values, download order, filesystem enumeration, or nondeterministic transforms.

The product MUST model dataset lineage as a DAG covering joins, filters, relabeling, deduplication, augmentation, synthetic generation, feature extraction, and derived datasets.

Descriptors MUST declare dependence boundaries such as subject, patient, user, household, document, scene, source media, site, device, geography, and time window.

## 5. Split artifacts

Every evaluated run MUST use an immutable split artifact containing:

- canonical sample IDs and assignments;
- algorithm and implementation version;
- seed;
- grouping and stratification keys;
- temporal/geographic cutoffs and embargo windows;
- inclusion/exclusion policy;
- duplicate-family handling;
- digest.

DATA-020: Implicit random splitting is forbidden.  
DATA-021: Row order and execution scheduling MUST NOT change membership.  
DATA-022: Dependence groups and duplicate families MUST remain in one outer partition.  
DATA-023: Temporal evaluation MUST prevent future-to-past leakage through features, labels, preprocessing windows, or availability timestamps.  
DATA-024: Exact and configured near-duplicate detection MUST cover resized/cropped media, excerpts, translated/paraphrased text, augmented variants, and multimodal counterparts.  
DATA-025: If train/validation/test or an equivalent nested protocol cannot be created, execution MUST be rejected.

## 6. Physical role isolation

Training/search processes may access training data only. Validation selection/calibration processes may access validation data under the frozen policy but cannot update training parameters unless a new training attempt is created. After selection is frozen, a dedicated final-refit evaluator may access train+validation under the exact predeclared refit policy but cannot compare alternatives or access test data. Only a separate confirmatory test evaluator may access test labels and test-derived artifacts; that evaluator cannot train, adapt, calibrate, select, or emit per-example/partial feedback.

Isolation MUST cover:

- raw data and caches;
- fitted preprocessing state;
- tokenizers/vocabularies;
- embeddings and feature stores;
- retrieval indexes;
- teacher predictions;
- replay buffers;
- checkpoints and population archives;
- logs, filenames, metadata, and diagnostics.

Repeated test queries, partial results, per-example correctness, subgroup hints, or leaderboard probing MUST invalidate confirmatory status unless governed by a versioned reusable-holdout protocol.

## 7. Preprocessing graph

Preprocessing MUST be an ordered, typed, versioned declarative graph. Steps are classified as stateless, train-fitted, label-fitted, or stochastic.

DATA-030: Fitted statistics, imputers, scalers, encoders, tokenizers, vocabularies, PCA, feature selection, class weights, calibration, thresholds, and target transforms MUST fit only within their authorized training scope.  
DATA-031: Nested validation MUST rebuild fitted state inside each inner fold.  
DATA-032: Target-derived training features MUST use out-of-fold values.  
DATA-033: Stochastic augmentation MUST have explicit per-root/per-worker/per-epoch/per-sample RNG derivation and replay policy.  
DATA-034: Evaluation transforms MUST be deterministic.  
DATA-035: Every fitted transform state MUST be serialized safely and content-addressed.

## 8. Task registry

A versioned task entry MUST define:

- input contract;
- target contract;
- prediction contract;
- admissible losses;
- batching/masking;
- output decoding;
- aggregation unit;
- supported modalities;
- invalid-output behavior.

V1 registries MUST accommodate classification, multilabel classification, regression, ranking, forecasting, sequence labeling, generation, reconstruction, anomaly detection, survival/time-to-event, graph-level, node-level, edge-level, and dense prediction when implementations are provided.

## 9. Metric registry

A metric entry MUST define:

- accepted target/prediction representation;
- direction, domain, range, units;
- weighting and reduction order;
- macro/micro/group/token/frame/task aggregation;
- tie policy and numerical precision;
- NaN/Inf, abstention, missing prediction, empty mask, zero denominator, and degenerate target behavior;
- uncertainty method;
- golden test vectors.

Native metric values MUST be retained. Any canonical utility transform MUST be monotone, versioned, documented, and reported alongside the native value.

## 10. External pretraining, retrieval, and contamination policy

Every pretrained model, tokenizer, embedding model, teacher, retrieval corpus, synthetic-data generator, and external feature producer MUST record:

- exact asset/revision/file digests;
- declared training-data cutoff and source documentation;
- known benchmark/dataset overlap statements;
- license and usage scope;
- whether the asset saw labels, examples, derivatives, translations, excerpts, or duplicate families from protected evaluation data;
- contamination status: `cleared | declared_overlap | suspected | unknown | prohibited`.

Unknown or suspected overlap does not automatically prohibit operational model building, but it MUST downgrade evidence to `contamination_unresolved` and block claims that depend on clean benchmark generalization. Declared overlap MUST be modeled as prior information, disclosed in recommendation evidence, and excluded from clean contender comparisons unless the benchmark policy explicitly permits it.

Retrieval indexes and generated/synthetic datasets are part of candidate data access and MUST obey the same split/provenance capability labels. Any external asset derived from protected validation or test data invalidates confirmatory evidence.

The acceptance oracle for contamination fixtures is the recorded status and eligibility transition: a clean exact-revision asset is decision-grade eligible; a declared-overlap asset follows the benchmark's explicit policy and is otherwise operational-only; an unknown/suspected asset is operational-only; a prohibited or protected-test-derived asset is ineligible.

## 11. Benchmark packs

A benchmark pack is an immutable versioned list of benchmark descriptor digests plus:

- admission purpose;
- supported claim type;
- budget policy;
- required backends/platforms;
- contender requirements;
- seed and repeat policy;
- minimum evidence quality;
- tie tolerances;
- weighting and missing-result policy.

Pack names MUST be namespaced and versioned. A bare human name MUST NOT resolve differently by caller.

## 12. Decision-grade gate

A data/benchmark result is decision-grade only if exact artifacts resolve, governance permits use, integrity checks pass, splits pass leakage checks, preprocessing scopes are valid, test access audit is clean, evaluator and metrics are exact versions, failures are reported, and the backend is qualified for the task/operator/precision combination.
