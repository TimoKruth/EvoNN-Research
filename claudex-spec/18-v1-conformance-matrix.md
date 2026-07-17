# 18 — V1 Conformance Matrix and Host Classes

This document removes ambiguity from “broad multimodal v1,” “supported host,” and “normal local load.” A release may support more combinations, but it MUST pass the minimum matrix below.

## 1. Mandatory product combinations

| Problem class | Minimum required tasks | Mac backend | Linux backend | Required portfolio branches | Deployment gate |
|---|---|---|---|---|---|
| Tabular | binary/multiclass classification; regression | MLX plus classical CPU | PyTorch or qualified MLX plus classical CPU | contenders, family, topology, primitive→topology seed transfer, ensemble/hybrid synthesis | native; Core ML positive case |
| Image | single-label classification; scalar or multilabel prediction | MLX | PyTorch CUDA/CPU or qualified MLX | contenders/pretrained, family, topology or hierarchy, adaptation, compression | native; Core ML positive and negative cases |
| Text | classification; embedding/regression | MLX | PyTorch or qualified MLX | pretrained/adaptation, family, ensemble | native; conditional Core ML |
| Audio | classification; scalar regression | MLX | PyTorch or qualified MLX | pretrained/adaptation, family, ensemble | native |
| Sequence/time series | sequence classification/regression; forecasting | MLX | PyTorch or qualified MLX | family, topology, hierarchy, ensemble | native; conditional Core ML |
| Compact causal LM | next-token modeling and local generation | MLX | PyTorch or qualified MLX | pretrained/adaptation, family, compression | native; conditional Core ML/ExecuTorch |
| Joined multimodal | supervised classification or regression using at least two modalities | MLX | PyTorch or qualified MLX | pretrained/family encoders, hierarchy or routing/fusion, ensemble | native |

All required portfolio branches across v1 are: contenders, family, topology, hierarchy, primitive/motif seed source, pretrained/adaptation, compression, ensemble/routing, and cross-strategy hybrid synthesis. A branch need not support every row, but each branch MUST have at least one decision-grade qualifying workflow and MUST advertise ineligibility elsewhere before execution.

## 2. Compact causal language model boundary

V1 causal LM support is limited to local single-host models and experiments with:

- maximum configured parameter count of 1 billion;
- maximum context length of 8,192 tokens unless a host profile explicitly raises it;
- text-only causal next-token training/adaptation and local generation;
- no distributed pretraining;
- no image/audio/video generation;
- no claim of foundation-model-scale pretraining.

The task registry may be extensible to additional generation tasks, but registry expressiveness does not imply shipped product support.

## 3. Minimum dataset characteristics for gates

Each modality gate includes:

- a tiny deterministic CI fixture;
- a medium local fixture large enough to exercise batching, failure, and multiple candidates;
- corrupt/invalid/leaking/adversarial fixtures;
- at least one real licensed dataset or reproducible public snapshot for scheduled qualification.

Multimodal gates include complete, missing, unmatched, duplicate, one-to-many, and temporally misaligned records.

## 4. Host classes

### H-MAC-CI

- Apple Silicon macOS supported by pinned MLX;
- 16 GiB unified memory minimum;
- 4 logical worker slots maximum in acceptance tests;
- tiny/medium fixtures only.

### H-MAC-PRO

- Apple Silicon;
- 32 GiB unified memory recommended minimum;
- sufficient disk for two concurrent medium jobs and checkpoints;
- Core ML tooling installed;
- scheduled broad multimodal qualification.

### H-LINUX-CPU

- x86_64 or arm64 qualified distribution;
- 16 GiB RAM minimum;
- qualified PyTorch/MLX CPU profile;
- portable and classical inference/training gates.

### H-LINUX-CUDA

- NVIDIA GPU with at least 16 GiB device memory for broad gate profile;
- qualified driver/CUDA/framework lock;
- 32 GiB host RAM minimum;
- scheduled broad multimodal qualification.

Exact OS, chip/GPU, driver, framework, and dependency versions are release metadata, not evergreen values in this specification.

## 5. Normal local load profile

The five-second UI/event target is measured at:

- 4 concurrent workers;
- 20 task-state events/second sustained, 100/second burst;
- 100,000 persisted events in the active project;
- 10,000 candidate/evaluation rows in the active job;
- one active Web client and one CLI watcher;
- one metadata writer and one active per-run evidence owner;
- p95 durable-event-to-UI visibility ≤ 5 seconds and p50 ≤ 1 second.

## 6. Storage and scheduler spike thresholds

- Metadata command p95 ≤ 250 ms under normal local load excluding long-running work.
- SQLite busy/lock retries MUST NOT exceed 1% of metadata transactions in the gate profile; otherwise PostgreSQL or a redesigned writer path is required.
- Evidence owner query p95 ≤ 1 second for default job summary and ≤ 3 seconds for 10,000-row leaderboard.
- Scheduler MUST not exceed declared worker/resource capacity.
- Host/process restart reconciliation MUST complete within 60 seconds for the gate project.

## 7. Installation and lifecycle acceptance

For every supported host class:

1. Clean install from documented release artifacts.
2. `evonn doctor` verifies required and optional capabilities.
3. Start/stop/restart preserves state.
4. Upgrade from previous supported minor version runs reviewed migrations and backup.
5. Failed upgrade can restore the pre-upgrade database/artifact metadata.
6. Uninstall instructions distinguish application removal from user data removal.
7. Data/cache/artifact locations are documented and configurable within security constraints.
8. Supported browsers are current stable Chromium, Firefox, and WebKit/Safari versions qualified by the release.
