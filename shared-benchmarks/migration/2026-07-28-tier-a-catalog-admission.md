# Tier A Catalog Admission — 2026-07-28

## Purpose

This record admits the Phase 0 Tier A benchmark identities into the frozen
`BenchmarkSpec` and `BenchmarkPack` v1 catalog. It records catalog metadata
only. It does not claim that EvoNN currently provides executable dataset
loaders, training runs, contender results, or scientific benchmark evidence.

Every admitted definition therefore has `status: planned` and the
`catalog_only` tag. Promotion to `implemented` requires separately reviewed
runtime loaders and tests.

## Immutable source

- Repository: `https://github.com/TimoKruth/EvoNN`
- Commit: `3652e0a32a907b51fb26a56fa9650ba258cb9054`
- Tier A source: `shared-benchmarks/suites/parity/tier_a_contract.yaml`
- Dataset metadata sources:
  - `shared-benchmarks/catalog/iris.yaml`
  - `shared-benchmarks/catalog/wine.yaml`
  - `shared-benchmarks/catalog/breast_cancer.yaml`
  - `shared-benchmarks/catalog/moons.yaml`
  - `shared-benchmarks/catalog/digits.yaml`
  - `shared-benchmarks/catalog/diabetes.yaml`
  - `shared-benchmarks/catalog/friedman1.yaml`
  - `shared-benchmarks/catalog/credit_g.yaml`

The exact commit, rather than a branch name or live repository state, is the
migration authority.

## Canonical identity mapping

| Predecessor dataset | Admitted canonical ID | Frozen-model mapping |
| --- | --- | --- |
| `iris` | `iris_classification` | sklearn `load_iris`; tabular shape `[4]`; 3 classes |
| `wine` | `wine_classification` | sklearn `load_wine`; tabular shape `[13]`; 3 classes |
| `breast_cancer` | `breast_cancer` | sklearn `load_breast_cancer`; tabular shape `[30]`; 2 classes |
| `moons` | `moons_classification` | sklearn `make_moons`; tabular shape `[2]`; 1,000 samples; noise `0.2`; 2 classes |
| `digits` | `digits_image` | sklearn `load_digits`; image shape `[8, 8]` (the predecessor records 64 flattened inputs); 10 classes |
| `diabetes` | `diabetes_regression` | sklearn `load_diabetes`; tabular shape `[10]`; scalar regression output |
| `friedman1` | `friedman1_regression` | sklearn `make_friedman1`; tabular shape `[10]`; 1,000 samples; noise `1.0`; scalar regression output |
| `credit_g` | `credit_g_classification` | OpenML dataset 31, target `class`; tabular shape `[20]`; 2 classes; finance domain |

The frozen schema has no dataset-source, generator-parameter, native-ID, or
domain fields. Those source facts remain in this admission record; compact
source-kind tags are descriptive only and do not establish runtime support.

## Field mapping

- Task kinds, primary metric names and directions, runtime classes, finite
  score ceilings, and required contender floors come from the predecessor
  Tier A contract.
- Classification uses `accuracy` with direction `max` and natural ceiling
  `1.0`; a ceiling tie is `not_evidence`.
- Regression uses `mse` with direction `min`; because the metric is unbounded,
  its ceiling value is `null` with `best_observed` tie policy.
- `budget_epochs` is 20, matching `epochs_per_candidate` in the predecessor.
- Required contender identifiers are UTF-8 sorted to satisfy the frozen model;
  their membership is unchanged.
- `tier1_core` and `tier_a_contract` use 64 evaluations. The
  `tier1_core_smoke` pack uses 16 evaluations over the same eight immutable
  benchmark identities. Each count divides evenly across the eight entries.
- All packs are symmetric Tier A packs and declare both `image` and `tabular`
  modalities.

## Claims explicitly not made

This admission does not assert that:

- any benchmark data can currently be loaded by this repository;
- any EvoNN engine or contender can currently execute these packs;
- required contender floors have been run or met;
- the smoke budget is sufficient for scientific comparison;
- any metric value, ranking, reproducibility result, or portability result
  exists.

Those claims require later runtime implementation and immutable run evidence.
