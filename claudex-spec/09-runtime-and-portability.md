# 09 — Runtime Backends and Cross-Platform Portability

## 1. Runtime strategy

EvoNN MUST use explicit backend protocols and capability negotiation. It MUST NOT pretend MLX and PyTorch are one uniform tensor framework or silently route unsupported operations through a fallback while preserving the same evidence class.

## 2. Apple Silicon

On supported Apple Silicon macOS systems:

- model tensor training and native inference MUST use MLX for MLX-qualified candidates;
- MLX version, macOS version, chip, memory, device policy, precision, compiler/runtime, and deterministic settings MUST be recorded;
- non-MLX libraries MAY perform decoding, parsing, classical estimators, metric calculation, or conversion when declared;
- a job requiring MLX MUST fail preflight if unavailable rather than silently substitute another runtime.

## 3. Linux

Linux is decision-grade from v1. Supported profiles MUST be explicitly qualified, such as:

- MLX CPU where feature/performance qualification passes;
- MLX CUDA where hardware and operator qualification passes;
- PyTorch CPU/CUDA for supported candidate classes;
- classical CPU runtimes.

Availability of an installable package alone does not establish qualification.

## 4. PyTorch role

PyTorch is the broad interoperability ecosystem for:

- pretrained/foundation models;
- Transformers/PEFT;
- Linux CUDA training where qualified;
- direct Core ML conversion paths;
- ONNX/ExecuTorch export where qualified;
- model implementations without MLX parity.

A PyTorch candidate is not automatically an MLX candidate. Conversion produces a new compiled artifact identity and requires parity validation.

## 5. Capability descriptor

A backend capability manifest MUST declare the following. Its `manifest_digest` is computed from canonical serialization with that field omitted, then attached to the record:

- OS/architecture/device requirements;
- package and driver versions;
- supported task and modality classes;
- operator set and dynamic-shape behavior;
- dtype/precision and quantization modes;
- optimizer/loss semantics;
- RNG/determinism class;
- checkpoint/serialization formats;
- measurement support;
- export targets;
- known deviations and quarantines.

## 6. Conformance

RUNTIME-001: Operator semantics MUST be tested with golden inputs and gradients where relevant.  
RUNTIME-002: Task-level training smoke tests MUST verify finite learning and metric behavior.  
RUNTIME-003: Cross-backend candidate parity MUST use declared numerical and task-statistical tolerances.  
RUNTIME-004: A failing task/operator/precision combination MUST be quarantined from decision-grade claims.  
RUNTIME-005: Unsupported operations MUST be rejected before expensive execution.  
RUNTIME-006: Cross-platform model serialization MUST preserve preprocessing, decoding, and registry bindings; lossy conversion creates a distinct candidate.

## 7. Determinism classes

- **D0 — unqualified:** no repeatability claim.
- **D1 — seeded statistical:** results reproduce within a declared distribution/tolerance.
- **D2 — same-host numerical:** same version/backend/hardware reproduces metrics and artifacts within tight tolerances.
- **D3 — bitwise:** exact artifact/event equivalence where feasible.

Every result MUST declare its determinism class and known nondeterministic operations.

## 8. Performance measurement

Performance comparisons MUST align:

- timing boundary;
- warm-up and compilation treatment;
- synchronization;
- batch/input shapes;
- precision;
- preprocessing/data transfer inclusion;
- thread/worker settings;
- power/thermal state where material;
- device and runtime versions.

Unlike measurements MUST NOT be ranked together without a visible qualification.

## 9. Runtime-native fallback

The guaranteed deployment target is a runtime-native EvoNN bundle. ONNX, Core ML, or ExecuTorch are conditional derived targets. Failure to convert MUST NOT invalidate a verified native bundle.

## 10. Supported-host matrix

Every release MUST publish a generated matrix listing tested macOS/Apple Silicon and Linux/CPU/CUDA combinations, exact dependency locks, qualified tasks/operators/precisions, known failures, and evidence dates.
