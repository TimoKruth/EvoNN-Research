# Configuration area

`standard.yaml` is the quality-first setup: the confirmed evolving v3 policy,
128 fits, 12 epochs, native MLX CPU and full-budget time allowances. Select
`--backend numpy_fallback` for portability. Fresh CLI/API runs with no policy
also select evolving; all eleven arms remain available through `--preset`.
See the [completed results](../../governance/stratograph-results-20260930.md).

Legacy smoke/core presets retain their original evaluator. `research_v2.yaml`
selects the normalized v2 proxy; `trainable_v2.yaml` selects differentiable shared
cells. Both are bounded research presets with scientific qualification pending.
See the [runtime settings](../README.md#explicit-version-2-research-execution),
central [capability table](../../README.md#current-capabilities) and
[execution plan](../../CONSOLIDATED_PLAN.md).

`attention_v3.yaml`, `dilated_v3.yaml` and `hybrid_v3.yaml` select fixed temporal
alternatives with the new representation/training controls. `evolving_v3.yaml`
also evolves those choices. See [v3 settings and comparison generation](../README.md#version-3-temporal-research).
These older research YAML files retain their small explicit allocations and
NumPy backend. Their policies were compared in the completed within-Stratograph
study; cross-engine and protected-test qualification remain separate.
