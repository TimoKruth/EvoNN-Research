# 11 — Deployment, Export, and Inference

## 1. Promotion prerequisites

A model may be promoted only when:

- exact candidate and evaluation artifacts resolve;
- required validation evidence is complete;
- hard constraints are satisfied or an explicit override is recorded;
- finalization/test policy is complete;
- model origin, licenses, and external assets are known;
- native inference can be reconstructed;
- required security scanning passes.

## 2. Native bundle

Every promoted model MUST produce a native bundle. The bundle MUST be self-describing and independently verifiable without the search run database. It MUST be dependency-complete: required bytes are either embedded or referenced by exact verified locally resolvable content digests. Both modes verify offline; missing dependencies fail verification.

Required contents:

- bundle manifest and digest;
- model specification and safe weights;
- preprocessing/postprocessing and fitted state;
- input/output/task schemas;
- labels/tokenizer/processor assets;
- runtime requirements;
- base model and adapter dependencies;
- lineage/provenance;
- evidence/model card;
- licenses/attributions;
- test vectors;
- checksums and optional signatures.

Raw training data MUST NOT be included by default.

## 3. Inference contract

The bundle MUST define:

- accepted inputs, shapes, types, units, optionality;
- missing/unseen value behavior;
- batching and padding;
- deterministic preprocessing;
- model invocation;
- output decoding;
- label ordering;
- calibration/thresholds;
- runtime errors;
- supported platforms/devices.

A local verification command MUST load the bundle safely, run test vectors, compare outputs to declared tolerances, and report compatibility/integrity.

## 4. Core ML

Core ML is a conditional deployment target.

DEP-001: Eligibility MUST be determined before conversion when Core ML is a constraint or preference.  
DEP-002: Eligibility covers operators, control flow, preprocessing, dynamic shapes, input types, precision, postprocessing, and minimum deployment target.  
DEP-003: Conversion MUST create a derived artifact identity.  
DEP-004: Conversion success alone is insufficient; parity validation is mandatory.  
DEP-005: Parity uses representative non-sensitive test vectors and declared absolute/relative/task tolerances.  
DEP-006: A parity-failing artifact is investigation-only and MUST NOT be marked verified.  
DEP-007: Core ML failure MUST NOT invalidate the native bundle.

## 5. Optional targets

ONNX Runtime and ExecuTorch MAY be supported when a candidate passes export and runtime qualification. They are not universal v1 guarantees.

The export service MUST report unsupported operators, graph fallback/partitioning, numerical drift, target runtime requirements, and performance measurements.

## 6. Classical models

Classical estimator persistence SHOULD use safe declarative formats such as skops where compatible. Unsafe Python serialization requires explicit trusted-local approval and cannot be distributed as an ordinary verified bundle.

## 7. Pretrained/adapters

An adapter bundle MUST bind to an exact base-model revision, tokenizer/processor, configuration, and file hashes. A small adapter alone MUST NOT be represented as a self-contained model.

Offline bundles MUST either include licensed base assets or require a content-addressed local dependency that verification can resolve.

## 8. Quantization and compression

Deployment transformations MUST report:

- source and derived candidate IDs;
- method/version;
- measured serialized size;
- actual parameter count;
- precision distribution;
- latency/memory environment;
- quality retention and calibration changes;
- parity/robustness findings.

Estimated size or energy proxies MUST be labeled estimates and MUST NOT be presented as measurements.

## 9. Deployment verification

Verification MUST include:

- integrity;
- safe format checks;
- dependency resolution;
- schema validation;
- numerical test vectors;
- preprocessing parity;
- output decoding;
- latency/memory smoke bounds when declared;
- no undeclared network dependency;
- license/attribution presence.

## 10. Drift and production handoff

The bundle SHOULD include monitoring guidance, feature/label schema fingerprints, expected ranges, calibration context, training data version, known limitations, and recommended drift signals. EvoNN v1 does not manage production deployment or live monitoring services.
