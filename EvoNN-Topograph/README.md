# EvoNN Topograph

See the central [capability table](../README.md#current-capabilities) and
[execution plan](../CONSOLIDATED_PLAN.md) for this package’s current scope.
Run `scripts/ci/topograph-checks.sh` from the repository root.

New Topograph runs default to the confirmed mixer configuration. It is also
available as `evonn-topograph run --preset mixer` or
`--config EvoNN-Topograph/configs/mixer.yaml`. It preserves the exact
settings from the completed 16-seed confirmation. `--preset next`, `open` and
`legacy` select explicit controls; presets cannot be mixed with another config
or resume request. Legacy requires explicit selection (`--preset legacy`, or
an explicit legacy variant in a configuration). Resume uses the saved policy,
including old unversioned legacy runs. Mixer improved aggregate real-text-heavy performance but
regressed on delayed copy; it is not a universal replacement. See the
[all-engine follow-up protocol](../governance/topograph-cross-engine-20260929.md).

The additive experimental policies, configuration and qualification limits are
documented under [Topograph research modes](../README.md#topograph-research-modes).
The unversioned legacy genome/compiler path remains available for historical replay.

The legacy Phase 4 text path predicts one next byte from a fixed preceding context.
A one-hot context feeds the trainable quantized DAG; all context tokens precede
the scored target. Replay recomputes perplexity. This is a window-conditioned
DAG, not a per-position causal Transformer implementation.
